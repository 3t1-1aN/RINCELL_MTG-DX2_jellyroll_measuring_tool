import json
import os
import time
import threading
from pathlib import Path
from queue import Queue

import gspread
import serial
import serial.tools.list_ports
from dotenv import load_dotenv, set_key
from flask import Flask, Response, jsonify, render_template, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ── Paths & env ───────────────────────────────────────────────────────────────
RINCELL_DIR = Path(__file__).resolve().parent
ENV_FILE = RINCELL_DIR / ".env"
load_dotenv(ENV_FILE)

def cfg(key, default):
    return os.environ.get(key, default)

CREDENTIALS_FILE = RINCELL_DIR / "credentials.json"
TOKEN_FILE       = RINCELL_DIR / "token.json"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)

# ── Live SSE log queue ────────────────────────────────────────────────────────
_log_queue: Queue = Queue()

def push_log(msg: str):
    _log_queue.put(msg)

# ── Settings helpers ──────────────────────────────────────────────────────────
def get_settings() -> dict:
    load_dotenv(ENV_FILE, override=True)
    return {
        "port":             cfg("PORT", "COM4"),
        "baud_rate":        int(cfg("BAUD_RATE", "9600")),
        "total_samples":    int(cfg("TOTAL_SAMPLES", "6")),
        "delay_seconds":    float(cfg("DELAY_SECONDS", "1.0")),
        "hw_refresh":       float(cfg("HARDWARE_REFRESH_SECONDS", "0.1")),
        "nominal_diameter": float(cfg("BATTERY_NOMINAL_DIAMETER_MM", "18.00")),
        "sheet_id":         cfg("GOOGLE_SHEET_ID", ""),
        "sheet_tab":        cfg("GOOGLE_SHEET_TAB", ""),
    }

def save_settings(data: dict):
    mapping = {
        "port":             "PORT",
        "baud_rate":        "BAUD_RATE",
        "total_samples":    "TOTAL_SAMPLES",
        "delay_seconds":    "DELAY_SECONDS",
        "hw_refresh":       "HARDWARE_REFRESH_SECONDS",
        "nominal_diameter": "BATTERY_NOMINAL_DIAMETER_MM",
        "sheet_id":         "GOOGLE_SHEET_ID",
        "sheet_tab":        "GOOGLE_SHEET_TAB",
    }
    for field, env_key in mapping.items():
        if field in data:
            set_key(str(ENV_FILE), env_key, str(data[field]))
    load_dotenv(ENV_FILE, override=True)

# ── Serial / measurement helpers ──────────────────────────────────────────────
def parse_measurement(raw: str) -> float:
    if ":" in raw:
        return float(raw.split(":")[1])
    return float("".join(c for c in raw if c.isdigit() or c in ".-"))

def to_actual_diameter(dev: float, nominal: float) -> float:
    return nominal + dev

def capture_samples(ser: serial.Serial, s: dict) -> list[float]:
    pts = []
    total   = s["total_samples"]
    nominal = s["nominal_diameter"]
    hw_ref  = s["hw_refresh"]
    delay   = s["delay_seconds"]

    for i in range(total):
        ser.reset_input_buffer()
        ser.write(b"R\r\n")
        time.sleep(hw_ref)
        ser.reset_input_buffer()
        ser.write(b"A\r\n")

        raw = ser.readline().decode("utf-8").strip()
        try:
            dev    = parse_measurement(raw)
            actual = to_actual_diameter(dev, nominal)
            pts.append(actual)
            sign   = "+" if dev >= 0 else "-"
            push_log(f"SAMPLE|{i+1}|{total}|{actual:.4f}|{nominal} {sign} {abs(dev):.4f}")
        except (ValueError, IndexError):
            push_log(f"WARN|Could not parse sample {i+1}. Raw: '{raw}'")

        if i < total - 1:
            time.sleep(max(0, delay - hw_ref))

    return pts

def build_header(n: int) -> list:
    return (["Battery Name", "Timestamp"]
            + [f"Sample {i} (mm)" for i in range(1, n + 1)]
            + ["Min (mm)", "Max (mm)", "TIR (mm)"])

def build_row(name: str, pts: list, mn: float, mx: float, tir: float) -> list:
    return ([name, time.strftime("%Y-%m-%d %H:%M:%S")]
            + [round(x, 4) for x in pts]
            + [round(mn, 4), round(mx, 4), round(tir, 4)])

# ── Google Sheets helpers ─────────────────────────────────────────────────────
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

def append_to_sheet(name: str, pts: list, mn: float, mx: float, tir: float, s: dict):
    sheet_id  = s["sheet_id"]
    sheet_tab = s["sheet_tab"]
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID is not set.")
    client = gspread.authorize(get_google_credentials())
    ss     = client.open_by_key(sheet_id)
    ws     = ss.worksheet(sheet_tab) if sheet_tab else ss.sheet1
    if not ws.acell("A1").value:
        ws.append_row(build_header(s["total_samples"]), value_input_option="USER_ENTERED")
    ws.append_row(build_row(name, pts, mn, mx, tir), value_input_option="USER_ENTERED")
    return sheet_id

# ── Background capture task ───────────────────────────────────────────────────
def _run_capture(battery_name: str, s: dict):
    push_log(f"INFO|Starting capture for: {battery_name}")
    push_log(f"INFO|Settings — {s['total_samples']} samples, {s['delay_seconds']}s delay, port {s['port']}")

    try:
        with serial.Serial(s["port"], s["baud_rate"], timeout=2, parity=serial.PARITY_NONE) as ser:
            pts = capture_samples(ser, s)
    except Exception as e:
        push_log(f"ERROR|Serial error: {e}")
        push_log("DONE|")
        return

    total = s["total_samples"]
    if len(pts) != total:
        push_log(f"ERROR|Only captured {len(pts)}/{total} samples. Aborting.")
        push_log("DONE|")
        return

    mn  = min(pts)
    mx  = max(pts)
    tir = mx - mn
    push_log(f"RESULT|{json.dumps({'points': pts, 'min': mn, 'max': mx, 'tir': tir, 'name': battery_name})}")

    try:
        sheet_id = append_to_sheet(battery_name, pts, mn, mx, tir, s)
        push_log(f"SAVED|{sheet_id}")
    except Exception as e:
        push_log(f"ERROR|Google Sheets error: {e}")

    push_log("DONE|")

# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ports")
def list_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return jsonify(ports)

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(get_settings())

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    save_settings(request.json)
    return jsonify({"ok": True})

@app.route("/api/capture", methods=["POST"])
def api_capture():
    body         = request.json or {}
    battery_name = (body.get("battery_name") or "").strip()
    if not battery_name:
        return jsonify({"error": "Battery name is required."}), 400

    s = get_settings()
    threading.Thread(target=_run_capture, args=(battery_name, s), daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/stream")
def api_stream():
    """SSE endpoint — streams log messages to the frontend."""
    def generate():
        while True:
            msg = _log_queue.get()
            yield f"data: {msg}\n\n"
            if msg.startswith("DONE|"):
                break
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)