from __future__ import annotations

import json
import re

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import CREDENTIALS_FILE, TOKEN_FILE
from .devices.diameter import diameter_sample_count

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


def _normalize_label(label: str) -> str:
    text = (label or "").strip().casefold()
    text = text.replace("θ", "deg").replace("°", "deg")
    return re.sub(r"\s+", " ", text)


def _canonical_key(label: str) -> str | None:
    text = _normalize_label(label)
    if not text:
        return None

    static = {
        "name": {"name", "battery name"},
        "jellyroll_id": {"jellyroll id", "id"},
        "wt": {"wt", "weight raw", "weight"},
        "min_mm": {"min d", "min mm", "min diameter (mm)", "min (mm)"},
        "min_deg": {"min deg", "min angle (deg)", "min angle"},
        "max_mm": {"max d", "max mm", "max diameter (mm)", "max (mm)"},
        "max_deg": {"max deg", "max angle (deg)", "max angle"},
        "avg_mm": {"avg", "avg d", "avg mm", "avg diameter (mm)", "average", "average diameter (mm)"},
        "tir": {"tir", "tir (mm)"},
        "tol": {"tol", "dtol", "tolerance (mm)", "tolerance", "diameter tolerance (mm)", "diameter tolerance"},
        "stat": {"stat", "status", "dstat", "diameter status"},
        "ostat": {"ostat", "overall status"},
    }
    for key, aliases in static.items():
        if text in aliases:
            return key

    sample_mm = re.fullmatch(r"(?:s|sample)\s*(\d+)(?:\s*\(mm\))?$", text)
    if sample_mm:
        return f"s{sample_mm.group(1)}_mm"

    sample_deg = re.fullmatch(r"(?:s|sample)\s*(\d+)\s*(?:deg|\(deg\)|angle \(deg\))", text)
    if sample_deg:
        return f"s{sample_deg.group(1)}_deg"

    return None


def _format_mm_value(value: float | None):
    return "" if value is None else round(float(value), 4)


def _sample_headers(n: int) -> list[str]:
    headers: list[str] = []
    for i in range(1, n + 1):
        headers.extend([f"S{i}", f"S{i}θ"])
    return headers


def _sample_header_aliases(sample_index: int) -> set[str]:
    return {
        f"S{sample_index}",
        f"S{sample_index} mm",
        f"S{sample_index}θ",
        f"S{sample_index} deg",
        f"Sample {sample_index} (mm)",
        f"Sample {sample_index}",
    }


def _build_canonical_values(
    result: dict,
    total_samples: int,
    *,
    name: str | None = None,
    jellyroll_id: str | None = None,
    weight_raw: str | None = None,
) -> dict[str, object]:
    values: dict[str, object] = {
        "name": name or "",
        "jellyroll_id": jellyroll_id or name or "",
        "wt": weight_raw or "",
        "min_mm": _format_mm_value(result["min"]),
        "min_deg": _format_angle_value(result.get("min_angle")),
        "max_mm": _format_mm_value(result["max"]),
        "max_deg": _format_angle_value(result.get("max_angle")),
        "avg_mm": _format_mm_value(result.get("avg")),
        "tir": round(result["tir"], 4),
        "tol": round(result["tolerance"], 4),
        "stat": "Pass" if result["pass"] else "Fail",
        "ostat": "Complete" if result["pass"] else "Check Diameter",
    }

    samples = result.get("samples") or []
    by_index = {int(sample["index"]): sample for sample in samples}
    points = result.get("points") or []

    for sample_index in range(1, total_samples + 1):
        sample = by_index.get(sample_index)
        if sample:
            value = sample["value"]
            angle = sample.get("angle")
        elif sample_index <= len(points):
            value = points[sample_index - 1]
            angle = None
        else:
            value = None
            angle = None

        values[f"s{sample_index}_mm"] = _format_mm_value(value)
        values[f"s{sample_index}_deg"] = _format_angle_value(angle)

    return values


def _values_lookup(canonical_values: dict[str, object], total_samples: int) -> dict[str, object]:
    """Exact header labels mapped to values, including common aliases."""
    lookup: dict[str, object] = {}

    def add(label: str, key: str) -> None:
        lookup[label] = canonical_values.get(key, "")

    add("Name", "name")
    add("Battery Name", "name")
    add("Jellyroll ID", "jellyroll_id")
    add("ID", "jellyroll_id")
    add("Wt", "wt")
    add("Weight Raw", "wt")
    add("Min D", "min_mm")
    add("Min mm", "min_mm")
    add("Min Diameter (mm)", "min_mm")
    add("Min θ", "min_deg")
    add("Min deg", "min_deg")
    add("Min Angle (deg)", "min_deg")
    add("Max D", "max_mm")
    add("Max mm", "max_mm")
    add("Max Diameter (mm)", "max_mm")
    add("Max θ", "max_deg")
    add("Max deg", "max_deg")
    add("Max Angle (deg)", "max_deg")
    add("Avg", "avg_mm")
    add("Avg D", "avg_mm")
    add("Avg mm", "avg_mm")
    add("Avg Diameter (mm)", "avg_mm")
    add("Average Diameter (mm)", "avg_mm")
    add("TIR", "tir")
    add("TIR (mm)", "tir")
    add("TOL", "tol")
    add("Tol", "tol")
    add("DTol", "tol")
    add("Tolerance (mm)", "tol")
    add("Diameter Tolerance (mm)", "tol")
    add("Status", "stat")
    add("Stat", "stat")
    add("DStat", "stat")
    add("Diameter Status", "stat")
    add("OStat", "ostat")
    add("Overall Status", "ostat")

    for sample_index in range(1, total_samples + 1):
        mm_key = f"s{sample_index}_mm"
        deg_key = f"s{sample_index}_deg"
        lookup[f"S{sample_index}"] = canonical_values.get(mm_key, "")
        lookup[f"S{sample_index} mm"] = canonical_values.get(mm_key, "")
        lookup[f"S{sample_index}θ"] = canonical_values.get(deg_key, "")
        lookup[f"S{sample_index} deg"] = canonical_values.get(deg_key, "")
        lookup[f"Sample {sample_index} (mm)"] = canonical_values.get(mm_key, "")
        lookup[f"Sample {sample_index} Angle (deg)"] = canonical_values.get(deg_key, "")

    return lookup


def _header_canonical_keys(header: list[str]) -> set[str]:
    keys: set[str] = set()
    for label in header:
        key = _canonical_key(label)
        if key:
            keys.add(key)
    return keys


def _merge_header(existing: list[str], preferred: list[str]) -> list[str]:
    """Keep the existing column order and append any preferred columns that are missing."""
    merged = [label for label in existing if label.strip()]
    seen = _header_canonical_keys(merged)
    for label in preferred:
        key = _canonical_key(label)
        if key:
            if key in seen:
                continue
            seen.add(key)
        elif label in merged:
            continue
        merged.append(label)
    return merged


def _resolve_header(ws, preferred_header: list[str]) -> list[str]:
    """Write preferred headers on blank sheets; extend existing sheets with missing columns."""
    existing = ws.get_all_values()
    if not existing:
        end_col = column_letter(len(preferred_header))
        ws.update(f"A1:{end_col}1", [preferred_header], value_input_option="RAW")
        return preferred_header

    current_header = existing[0]
    if not any(cell.strip() for cell in current_header):
        end_col = column_letter(len(preferred_header))
        ws.update(f"A1:{end_col}1", [preferred_header], value_input_option="RAW")
        return preferred_header

    merged = _merge_header(current_header, preferred_header)
    if merged != [label for label in current_header if label.strip()] and len(merged) > len([label for label in current_header if label.strip()]):
        end_col = column_letter(len(merged))
        ws.update(f"A1:{end_col}1", [merged], value_input_option="RAW")
    return merged if merged else current_header


def build_diameter_header(n: int) -> list[str]:
    return [
        "Name",
        "Min D",
        "Min θ",
        "Max D",
        "Max θ",
        "TIR",
        "TOL",
        "Status",
        *_sample_headers(n),
        "Avg",
    ]


def build_diameter_values(name: str, result: dict, total_samples: int) -> dict[str, object]:
    canonical = _build_canonical_values(result, total_samples, name=name)
    return _values_lookup(canonical, total_samples)


def build_line_header(total_samples: int) -> list[str]:
    return [
        "Jellyroll ID",
        "Wt",
        "Min D",
        "Min θ",
        "Max D",
        "Max θ",
        "TIR",
        "TOL",
        "Status",
        *_sample_headers(total_samples),
        "Avg",
    ]


def build_line_values(
    jellyroll_id: str,
    result: dict,
    total_samples: int,
    weight_reading: dict | None = None,
) -> dict[str, object]:
    canonical = _build_canonical_values(
        result,
        total_samples,
        jellyroll_id=jellyroll_id,
        weight_raw=weight_reading["raw"] if weight_reading else "",
    )
    return _values_lookup(canonical, total_samples)


def _ensure_header_if_empty(ws, preferred_header: list[str]) -> list[str]:
    return _resolve_header(ws, preferred_header)


def _row_from_header(header: list[str], values_by_name: dict[str, object]) -> list:
    """Map header labels onto values using exact names, aliases, and canonical keys."""
    canonical_values: dict[str, object] = {}
    for label, value in values_by_name.items():
        key = _canonical_key(label)
        if key:
            canonical_values[key] = value

    row: list = []
    for label in header:
        if _is_timestamp_header(label):
            row.append("")
            continue
        if label in values_by_name:
            row.append(values_by_name[label])
            continue
        key = _canonical_key(label)
        if key and key in canonical_values:
            row.append(canonical_values[key])
            continue
        row.append("")
    return row


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
    "Stat",
    "Status",
    "DStat",
    "OStat",
    "Diameter Status",
    "Overall Status",
}


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
    if len(row) < len(header):
        row.extend([""] * (len(header) - len(row)))
    width = max(len(header), len(row), 1)
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
    sample_count = result.get("diameter_count") or diameter_sample_count(settings["total_samples"])
    preferred_header = build_diameter_header(sample_count)
    values = build_diameter_values(name, result, sample_count)
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
    sample_count = result.get("diameter_count") or diameter_sample_count(settings["total_samples"])
    preferred_header = build_line_header(sample_count)
    values = build_line_values(
        jellyroll_id,
        result,
        sample_count,
        weight_reading,
    )
    return _append_mapped_row(ws, preferred_header, values, result=result)
