from __future__ import annotations

import json

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import CREDENTIALS_FILE, TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _token_has_required_scopes(token_path) -> bool:
    if not token_path.exists():
        return False
    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    granted = set(token_data.get("scopes") or [])
    return set(SCOPES).issubset(granted)


def _desktop_oauth() -> UserCredentials:
    config = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    if "installed" not in config:
        raise ValueError("credentials.json must be a Desktop OAuth client.")
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    return flow.run_local_server(port=0, open_browser=True)


def get_google_credentials():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(f"Missing: {CREDENTIALS_FILE}")
    raw = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    if raw.get("type") == "service_account":
        return ServiceAccountCredentials.from_service_account_file(str(CREDENTIALS_FILE), scopes=SCOPES)

    creds = None
    if TOKEN_FILE.exists() and not _token_has_required_scopes(TOKEN_FILE):
        TOKEN_FILE.unlink()

    if TOKEN_FILE.exists():
        creds = UserCredentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                if TOKEN_FILE.exists():
                    TOKEN_FILE.unlink()
                creds = _desktop_oauth()
        else:
            if TOKEN_FILE.exists():
                TOKEN_FILE.unlink()
            creds = _desktop_oauth()
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _worksheet(sheet_id: str, sheet_tab: str):
    if not sheet_id:
        raise ValueError("Google Sheet ID is not set.")
    client = gspread.authorize(get_google_credentials())
    ss = client.open_by_key(sheet_id)
    return ss.worksheet(sheet_tab) if sheet_tab else ss.sheet1


def _format_angle_value(angle: float | None):
    return "" if angle is None else round(float(angle), 4)


def _is_timestamp_header(label: str) -> bool:
    text = (label or "").strip().lower()
    return "timestamp" in text or text in {"time", "date", "datetime"}


def _sample_headers(n: int) -> list[str]:
    return [f"Sample {i}" for i in range(1, n + 1)]


def _format_sample_cell(value: float, angle: float | None) -> str:
    diameter = f"{round(float(value), 4):.4f}"
    angle_text = _format_angle_value(angle)
    if angle_text == "":
        return diameter
    return f"{diameter} | {angle_text}"


def _sample_row_values(result: dict, n: int) -> list:
    samples = result.get("samples") or []
    by_index = {int(sample["index"]): sample for sample in samples}
    points = result.get("points") or []
    values: list = []

    for i in range(1, n + 1):
        sample = by_index.get(i)
        if sample:
            values.append(_format_sample_cell(sample["value"], sample.get("angle")))
            continue
        if i <= len(points):
            values.append(_format_sample_cell(points[i - 1], None))
            continue
        values.append("")

    return values


def _sample_header_aliases(sample_index: int) -> set[str]:
    """Accepted header names for a combined sample cell on new or older sheets."""
    return {
        f"Sample {sample_index}",
        f"Sample {sample_index} (mm)",
        f"Sample {sample_index} (mm | deg)",
        f"Sample {sample_index} (mm|deg)",
    }


def build_diameter_header(n: int) -> list[str]:
    return [
        "Battery Name",
        "Min Diameter (mm)",
        "Min Angle (deg)",
        "Max Diameter (mm)",
        "Max Angle (deg)",
        "Avg Diameter (mm)",
        "TIR (mm)",
        "Tolerance (mm)",
        "Status",
        *_sample_headers(n),
    ]


def build_diameter_values(name: str, result: dict, total_samples: int) -> dict[str, object]:
    values: dict[str, object] = {
        "Battery Name": name,
        "Min Diameter (mm)": round(result["min"], 4),
        "Min Angle (deg)": _format_angle_value(result.get("min_angle")),
        "Max Diameter (mm)": round(result["max"], 4),
        "Max Angle (deg)": _format_angle_value(result.get("max_angle")),
        "Avg Diameter (mm)": round(result["avg"], 4),
        "TIR (mm)": round(result["tir"], 4),
        "Tolerance (mm)": round(result["tolerance"], 4),
        "Status": "Pass" if result["pass"] else "Fail",
    }
    sample_headers = _sample_headers(total_samples)
    sample_values = _sample_row_values(result, total_samples)
    for header, value in zip(sample_headers, sample_values):
        values[header] = value
        # Keep older separate sample columns filled if the sheet still uses them.
        sample_index = int(header.split()[1])
        values[f"Sample {sample_index} (mm)"] = value
        values[f"Sample {sample_index} (mm | deg)"] = value
        values[f"Sample {sample_index} Angle (deg)"] = ""
    return values


def build_line_header(total_samples: int) -> list[str]:
    return [
        "Jellyroll ID",
        "Weight Raw",
        "Min Diameter (mm)",
        "Min Angle (deg)",
        "Max Diameter (mm)",
        "Max Angle (deg)",
        "Avg Diameter (mm)",
        "TIR (mm)",
        "Diameter Tolerance (mm)",
        "Diameter Status",
        "Overall Status",
        *_sample_headers(total_samples),
    ]


def build_line_values(
    jellyroll_id: str,
    result: dict,
    total_samples: int,
    weight_reading: dict | None = None,
) -> dict[str, object]:
    values: dict[str, object] = {
        "Jellyroll ID": jellyroll_id,
        "Weight Raw": weight_reading["raw"] if weight_reading else "",
        "Min Diameter (mm)": round(result["min"], 4),
        "Min Angle (deg)": _format_angle_value(result.get("min_angle")),
        "Max Diameter (mm)": round(result["max"], 4),
        "Max Angle (deg)": _format_angle_value(result.get("max_angle")),
        "Avg Diameter (mm)": round(result["avg"], 4),
        "TIR (mm)": round(result["tir"], 4),
        "Diameter Tolerance (mm)": round(result["tolerance"], 4),
        "Diameter Status": "Pass" if result["pass"] else "Fail",
        "Overall Status": "Complete" if result["pass"] else "Check Diameter",
    }
    sample_headers = _sample_headers(total_samples)
    sample_values = _sample_row_values(result, total_samples)
    for header, value in zip(sample_headers, sample_values):
        values[header] = value
        sample_index = int(header.split()[1])
        values[f"Sample {sample_index} (mm)"] = value
        values[f"Sample {sample_index} (mm | deg)"] = value
        values[f"Sample {sample_index} Angle (deg)"] = ""
    return values


def _ensure_header_if_empty(ws, preferred_header: list[str]) -> list[str]:
    """Only write a header on a blank sheet. Never rewrite existing headers or rows."""
    existing = ws.get_all_values()
    if not existing:
        end_col = column_letter(len(preferred_header))
        ws.update(f"A1:{end_col}1", [preferred_header], value_input_option="RAW")
        return preferred_header

    current_header = existing[0]
    if any(cell.strip() for cell in current_header):
        return current_header

    end_col = column_letter(len(preferred_header))
    ws.update(f"A1:{end_col}1", [preferred_header], value_input_option="RAW")
    return preferred_header


RED_TEXT = {
    "textFormat": {
        "foregroundColor": {
            "red": 0.8,
            "green": 0.0,
            "blue": 0.0,
        },
        "bold": True,
    }
}

GREEN_TEXT = {
    "textFormat": {
        "foregroundColor": {
            "red": 0.0,
            "green": 0.55,
            "blue": 0.0,
        },
        "bold": True,
    }
}

STATUS_FAIL_HEADERS = {
    "Status",
    "Diameter Status",
    "Overall Status",
}


def _row_from_header(header: list[str], values_by_name: dict[str, object]) -> list:
    """Map named values onto the sheet's existing header. Timestamp columns stay blank."""
    row: list = []
    for label in header:
        if _is_timestamp_header(label):
            row.append("")
            continue
        row.append(values_by_name.get(label, ""))
    return row


def _sample_deviation_by_index(result: dict) -> dict[int, float]:
    """Return sample index -> signed deviation from nominal (mm)."""
    deviations: dict[int, float] = {}
    nominal = result.get("nominal")
    for sample in result.get("samples") or []:
        index = int(sample["index"])
        if sample.get("deviation") is not None:
            deviations[index] = float(sample["deviation"])
            continue
        if nominal is not None and sample.get("value") is not None:
            deviations[index] = float(sample["value"]) - float(nominal)
    return deviations


def _out_of_tol_format_requests(header: list[str], row_number: int, result: dict) -> list[dict]:
    """Build format requests: red for undersize, green for oversize, red for fail status."""
    requests: list[dict] = []
    deviations = _sample_deviation_by_index(result)
    tolerance = float(result.get("tolerance") or 0.0)
    passed = bool(result.get("pass", True))

    for col_index, label in enumerate(header, start=1):
        cell = f"{column_letter(col_index)}{row_number}"
        text = (label or "").strip()

        if text in STATUS_FAIL_HEADERS and not passed:
            requests.append({"range": cell, "format": RED_TEXT})
            continue

        for sample_index, deviation in deviations.items():
            if abs(deviation) <= tolerance:
                continue
            if text not in _sample_header_aliases(sample_index):
                continue
            # Too small vs nominal -> red; too big vs nominal -> green.
            style = RED_TEXT if deviation < 0 else GREEN_TEXT
            requests.append({"range": cell, "format": style})
            break

    return requests


def _format_out_of_tol_cells(ws, header: list[str], row_number: int, result: dict) -> None:
    requests = _out_of_tol_format_requests(header, row_number, result)
    if not requests:
        return
    ws.batch_format(requests)


def _append_mapped_row(
    ws,
    preferred_header: list[str],
    values_by_name: dict[str, object],
    result: dict | None = None,
) -> int:
    header = _ensure_header_if_empty(ws, preferred_header)
    row = _row_from_header(header, values_by_name)

    # If this is a brand-new preferred header with no timestamp columns, keep that layout.
    # If the existing sheet still has older columns (including Timestamp), preserve them and
    # leave timestamp cells blank so old rows are never shifted or rewritten.
    existing = ws.get_all_values()
    row_number = max(len(existing), 1) + 1
    width = max(len(row), 1)
    end_col = column_letter(width)
    ws.update(
        f"A{row_number}:{end_col}{row_number}",
        [row],
        value_input_option="RAW",
    )
    if result is not None:
        _format_out_of_tol_cells(ws, header, row_number, result)
    return row_number


def append_diameter_result(name: str, result: dict, settings: dict) -> str:
    ws = _worksheet(settings["sheet_id"], settings["sheet_tab"])
    preferred_header = build_diameter_header(settings["total_samples"])
    values = build_diameter_values(name, result, settings["total_samples"])
    _append_mapped_row(ws, preferred_header, values, result=result)
    return settings["sheet_id"]


def append_weight_result(sample_name: str, reading: dict, settings: dict) -> str:
    sheet_id = settings["ohaus_sheet_id"]
    sheet_tab = settings["ohaus_sheet_tab"]
    ws = _worksheet(sheet_id, sheet_tab)
    preferred_header = ["Sample Name", "Weight Raw"]
    values = {
        "Sample Name": sample_name,
        "Weight Raw": reading["raw"],
    }
    _append_mapped_row(ws, preferred_header, values)
    return sheet_id


def create_or_update_weight_row(jellyroll_id: str, reading: dict, settings: dict) -> None:
    """Weight is stored in app state and written with the next diameter capture."""
    return None


def append_line_diameter_result(
    jellyroll_id: str,
    result: dict,
    settings: dict,
    weight_reading: dict | None = None,
) -> int:
    ws = _worksheet(settings["sheet_id"], settings["sheet_tab"])
    preferred_header = build_line_header(settings["total_samples"])
    values = build_line_values(
        jellyroll_id,
        result,
        settings["total_samples"],
        weight_reading,
    )
    return _append_mapped_row(ws, preferred_header, values, result=result)
