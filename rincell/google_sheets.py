from __future__ import annotations

import json
import time

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import CREDENTIALS_FILE, TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


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
    if TOKEN_FILE.exists():
        creds = UserCredentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
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


def _update_header(ws, header: list[str], current_header: list[str]) -> None:
    if current_header == header:
        return
    width = max(len(header), len(current_header), 1)
    end_col = column_letter(width)
    ws.update(f"A1:{end_col}1", [header + [""] * (width - len(header))], value_input_option="USER_ENTERED")


def build_diameter_header(n: int) -> list:
    return [
        "Battery Name",
        "Timestamp",
        "Min Diameter (mm)",
        "Min Angle (deg)",
        "Max Diameter (mm)",
        "Max Angle (deg)",
        "TIR (mm)",
        "Tolerance (mm)",
        "Status",
    ]


def build_diameter_row(name: str, result: dict) -> list:
    return [
        name,
        time.strftime("%Y-%m-%d %H:%M:%S"),
        round(result["min"], 4),
        _format_angle_value(result.get("min_angle")),
        round(result["max"], 4),
        _format_angle_value(result.get("max_angle")),
        round(result["tir"], 4),
        round(result["tolerance"], 4),
        "Pass" if result["pass"] else "Fail",
    ]


def append_diameter_result(name: str, result: dict, settings: dict) -> str:
    ws = _worksheet(settings["sheet_id"], settings["sheet_tab"])
    header = build_diameter_header(settings["total_samples"])
    current_header = ws.row_values(1)
    _update_header(ws, header, current_header)
    ws.append_row(build_diameter_row(name, result), value_input_option="USER_ENTERED")
    return settings["sheet_id"]


def append_weight_result(sample_name: str, reading: dict, settings: dict) -> str:
    sheet_id = settings["ohaus_sheet_id"]
    sheet_tab = settings["ohaus_sheet_tab"]
    ws = _worksheet(sheet_id, sheet_tab)
    header = ["Sample Name", "Timestamp", "Weight Raw"]
    current_header = ws.row_values(1)
    _update_header(ws, header, current_header)
    ws.append_row([sample_name, reading["timestamp"], reading["raw"]], value_input_option="USER_ENTERED")
    return sheet_id


def build_line_header(total_samples: int) -> list[str]:
    return [
        "Jellyroll ID",
        "Weight Timestamp",
        "Weight Raw",
        "Diameter Timestamp",
        "Min Diameter (mm)",
        "Min Angle (deg)",
        "Max Diameter (mm)",
        "Max Angle (deg)",
        "TIR (mm)",
        "Diameter Tolerance (mm)",
        "Diameter Status",
        "Overall Status",
    ]


def _line_worksheet(settings: dict):
    sheet_id = settings["sheet_id"]
    sheet_tab = settings["sheet_tab"]
    ws = _worksheet(sheet_id, sheet_tab)
    header = build_line_header(settings["total_samples"])
    current_header = ws.row_values(1)
    _update_header(ws, header, current_header)
    return ws, header


def _ensure_line_row(ws, header: list[str], jellyroll_id: str) -> int:
    row = [""] * len(header)
    row[0] = jellyroll_id
    row[-1] = "Waiting for Weight"
    ws.append_row(row, value_input_option="USER_ENTERED")
    return len(ws.col_values(1))


def create_or_update_weight_row(jellyroll_id: str, reading: dict, settings: dict) -> int:
    ws, header = _line_worksheet(settings)
    row_number = _ensure_line_row(ws, header, jellyroll_id)
    row_values = [
        jellyroll_id,
        reading["timestamp"],
        reading["raw"],
    ]
    ws.update(f"A{row_number}:C{row_number}", [row_values], value_input_option="USER_ENTERED")
    overall_col = column_letter(len(header))
    ws.update(f"{overall_col}{row_number}", [["Waiting for Diameter"]], value_input_option="USER_ENTERED")
    return row_number


def update_diameter_row(jellyroll_id: str, result: dict, settings: dict, row_number: int | None = None) -> int:
    ws, header = _line_worksheet(settings)
    row_number = row_number or _ensure_line_row(ws, header, jellyroll_id)
    diameter_values = [
        time.strftime("%Y-%m-%d %H:%M:%S"),
        round(result["min"], 4),
        _format_angle_value(result.get("min_angle")),
        round(result["max"], 4),
        _format_angle_value(result.get("max_angle")),
        round(result["tir"], 4),
        round(result["tolerance"], 4),
        "Pass" if result["pass"] else "Fail",
        "Complete" if result["pass"] else "Check Diameter",
    ]
    start_col = column_letter(4)
    end_col = column_letter(len(header))
    ws.update(f"{start_col}{row_number}:{end_col}{row_number}", [diameter_values], value_input_option="USER_ENTERED")
    return row_number
