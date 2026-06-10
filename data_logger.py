import json
import os
import time
from pathlib import Path

import gspread
import serial
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

RINCELL_DIR = Path(__file__).resolve().parent
load_dotenv(RINCELL_DIR / ".env")

# Test settings — change here or in Rincell/.env (env overrides these defaults)
TOTAL_SAMPLES = int(os.environ.get("TOTAL_SAMPLES", "6"))
DELAY_SECONDS = float(os.environ.get("DELAY_SECONDS", "1.0"))
HARDWARE_REFRESH_SECONDS = float(os.environ.get("HARDWARE_REFRESH_SECONDS", "0.1"))
BATTERY_NOMINAL_DIAMETER_MM = float(os.environ.get("BATTERY_NOMINAL_DIAMETER_MM", "18.00"))

PORT = "COM4"
BAUD_RATE = 9600

CREDENTIALS_FILE = RINCELL_DIR / "credentials.json"
TOKEN_FILE = RINCELL_DIR / "token.json"
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_TAB = os.environ.get("GOOGLE_SHEET_TAB", "")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def build_header(sample_count: int = TOTAL_SAMPLES) -> list[str]:
    return (
        ["Battery Name", "Timestamp"]
        + [f"Sample {i} (mm)" for i in range(1, sample_count + 1)]
        + ["Min (mm)", "Max (mm)", "TIR (mm)"]
    )


def parse_measurement(raw_response: str) -> float:
    """Parse gauge response; format is 'channel:reading:...' or plain numeric text."""
    if ":" in raw_response:
        return float(raw_response.split(":")[1])
    cleaned = "".join(c for c in raw_response if c.isdigit() or c in ".-")
    return float(cleaned)


def to_actual_diameter(captured_deviation_mm: float) -> float:
    """Convert gauge deviation to actual battery diameter (nominal ± captured value)."""
    return BATTERY_NOMINAL_DIAMETER_MM + captured_deviation_mm


def capture_samples(ser: serial.Serial) -> list[float]:
    data_points: list[float] = []

    for i in range(TOTAL_SAMPLES):
        ser.reset_input_buffer()
        ser.write(b"R\r\n")
        time.sleep(HARDWARE_REFRESH_SECONDS)
        ser.reset_input_buffer()
        ser.write(b"A\r\n")

        raw_response = ser.readline().decode("utf-8").strip()
        try:
            captured = parse_measurement(raw_response)
            actual = to_actual_diameter(captured)
            data_points.append(actual)
            print(
                f"  Sample {i + 1}/{TOTAL_SAMPLES}: {actual:.4f} mm "
                f"(nominal {BATTERY_NOMINAL_DIAMETER_MM} {'+' if captured >= 0 else '-'} {abs(captured):.4f})"
            )
        except (ValueError, IndexError):
            print(f"  Warning: Could not parse line. Raw data was: '{raw_response}'")

        if i < TOTAL_SAMPLES - 1:
            time.sleep(DELAY_SECONDS - HARDWARE_REFRESH_SECONDS)

    return data_points


def build_row(battery_name: str, data_points: list[float], min_val: float, max_val: float, tir_value: float) -> list:
    return (
        [battery_name, time.strftime("%Y-%m-%d %H:%M:%S")]
        + [round(x, 4) for x in data_points]
        + [round(min_val, 4), round(max_val, 4), round(tir_value, 4)]
    )


def _run_desktop_oauth_flow() -> UserCredentials:
    config = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    if "installed" not in config:
        raise ValueError(
            "credentials.json must be a Desktop OAuth client (with an 'installed' section). "
            "In Google Cloud Console: Credentials → Create OAuth client ID → Desktop app."
        )
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    print("\nOpening browser to sign in to Google (one-time setup)...")
    return flow.run_local_server(port=0, open_browser=True)


def get_google_credentials():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(f"Missing Google credentials file: {CREDENTIALS_FILE}")

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
            creds = _run_desktop_oauth_flow()
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_worksheet():
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set in Rincell/.env")

    client = gspread.authorize(get_google_credentials())
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    if GOOGLE_SHEET_TAB:
        return spreadsheet.worksheet(GOOGLE_SHEET_TAB)
    return spreadsheet.sheet1


def ensure_header(worksheet) -> None:
    first_cell = worksheet.acell("A1").value
    if not first_cell:
        worksheet.append_row(build_header(), value_input_option="USER_ENTERED")


def append_to_sheet(battery_name: str, data_points: list[float], min_val: float, max_val: float, tir_value: float) -> None:
    worksheet = get_worksheet()
    ensure_header(worksheet)
    worksheet.append_row(
        build_row(battery_name, data_points, min_val, max_val, tir_value),
        value_input_option="USER_ENTERED",
    )


def main() -> None:
    battery_name = input("Enter battery name: ").strip()
    if not battery_name:
        print("No battery name entered, aborting.")
        return

    print(f"\nOpening {PORT}... Ready to test {battery_name}.")
    print(f"Settings: {TOTAL_SAMPLES} samples, {DELAY_SECONDS}s delay between samples.")

    try:
        with serial.Serial(PORT, BAUD_RATE, timeout=2, parity=serial.PARITY_NONE) as ser:
            data_points = capture_samples(ser)
    except Exception as e:
        print(f"Error connecting to gauge: {e}")
        return

    if len(data_points) != TOTAL_SAMPLES:
        print(f"\nTest failed: Only captured {len(data_points)}/{TOTAL_SAMPLES} points.")
        return

    min_val = min(data_points)
    max_val = max(data_points)
    tir_value = max_val - min_val

    print(f"\n--- TEST COMPLETE: {battery_name} ---")
    print(f"All Captured Points: {data_points}")
    print(f"Min Reading:         {min_val:.4f} mm")
    print(f"Max Reading:         {max_val:.4f} mm")
    print(f"TIR (Out of Round):  {tir_value:.4f} mm")

    try:
        append_to_sheet(battery_name, data_points, min_val, max_val, tir_value)
    except Exception as e:
        print(f"\nError saving to Google Sheets: {e}")
        return

    print(f"\nData saved to Google Sheet under '{battery_name}'.")
    print(f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit")


if __name__ == "__main__":
    main()
