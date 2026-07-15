from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv, set_key


def app_root() -> Path:
    """Return the writable app folder for source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def asset_root() -> Path:
    """Return the folder where bundled templates/static files live."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_root()


RINCELL_DIR = app_root()
ASSET_DIR = asset_root()
ENV_FILE = RINCELL_DIR / ".env"
CREDENTIALS_FILE = RINCELL_DIR / "credentials.json"
TOKEN_FILE = RINCELL_DIR / "token.json"

load_dotenv(ENV_FILE)


def cfg(key: str, default: str) -> str:
    return os.environ.get(key, default)


def get_settings() -> dict[str, Any]:
    load_dotenv(ENV_FILE, override=True)
    return {
        "port": cfg("PORT", "COM4"),
        "baud_rate": int(cfg("BAUD_RATE", "9600")),
        "total_samples": int(cfg("TOTAL_SAMPLES", "12")),
        "delay_seconds": float(cfg("DELAY_SECONDS", "1.0")),
        "hw_refresh": float(cfg("HARDWARE_REFRESH_SECONDS", "0.1")),
        "nominal_diameter": float(cfg("BATTERY_NOMINAL_DIAMETER_MM", "17.5")),
        "tolerance_mm": float(cfg("DIAMETER_TOLERANCE_MM", "0.15")),
        "sheet_id": cfg("GOOGLE_SHEET_ID", ""),
        "sheet_tab": cfg("GOOGLE_SHEET_TAB", ""),
        "motor_port": cfg("MOTOR_PORT", ""),
        "motor_baud_rate": int(cfg("MOTOR_BAUD_RATE", "9600")),
        "motor_timeout_seconds": float(cfg("MOTOR_TIMEOUT_SECONDS", "10.0")),
        "ohaus_port": cfg("OHAUS_PORT", cfg("PORT", "COM4")),
        "ohaus_baud_rate": int(cfg("OHAUS_BAUD_RATE", cfg("BAUD_RATE", "9600"))),
        "ohaus_mode": cfg("OHAUS_MODE", "listen"),
        "ohaus_command": cfg("OHAUS_COMMAND", "IP"),
        "ohaus_interval": float(cfg("OHAUS_INTERVAL", "1.0")),
        "ohaus_sheet_id": cfg("OHAUS_GOOGLE_SHEET_ID", cfg("GOOGLE_SHEET_ID", "")),
        "ohaus_sheet_tab": cfg("OHAUS_GOOGLE_SHEET_TAB", "Weights"),
    }


def save_settings(data: dict[str, Any]) -> None:
    mapping = {
        "port": "PORT",
        "baud_rate": "BAUD_RATE",
        "total_samples": "TOTAL_SAMPLES",
        "delay_seconds": "DELAY_SECONDS",
        "hw_refresh": "HARDWARE_REFRESH_SECONDS",
        "nominal_diameter": "BATTERY_NOMINAL_DIAMETER_MM",
        "tolerance_mm": "DIAMETER_TOLERANCE_MM",
        "sheet_id": "GOOGLE_SHEET_ID",
        "sheet_tab": "GOOGLE_SHEET_TAB",
        "motor_port": "MOTOR_PORT",
        "motor_baud_rate": "MOTOR_BAUD_RATE",
        "motor_timeout_seconds": "MOTOR_TIMEOUT_SECONDS",
        "ohaus_port": "OHAUS_PORT",
        "ohaus_baud_rate": "OHAUS_BAUD_RATE",
        "ohaus_mode": "OHAUS_MODE",
        "ohaus_command": "OHAUS_COMMAND",
        "ohaus_interval": "OHAUS_INTERVAL",
        "ohaus_sheet_id": "OHAUS_GOOGLE_SHEET_ID",
        "ohaus_sheet_tab": "OHAUS_GOOGLE_SHEET_TAB",
    }
    ENV_FILE.touch(exist_ok=True)
    for field, env_key in mapping.items():
        if field in data:
            set_key(str(ENV_FILE), env_key, str(data[field]))
    load_dotenv(ENV_FILE, override=True)


def settings_with_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    s = get_settings()
    if not overrides:
        return s

    casts = {
        "baud_rate": int,
        "total_samples": int,
        "delay_seconds": float,
        "hw_refresh": float,
        "nominal_diameter": float,
        "tolerance_mm": float,
        "motor_baud_rate": int,
        "motor_timeout_seconds": float,
        "ohaus_baud_rate": int,
        "ohaus_interval": float,
    }
    for key, cast in casts.items():
        if key in overrides and overrides[key] not in (None, ""):
            s[key] = cast(overrides[key])

    for key in (
        "port",
        "sheet_id",
        "sheet_tab",
        "motor_port",
        "ohaus_port",
        "ohaus_mode",
        "ohaus_command",
        "ohaus_sheet_id",
        "ohaus_sheet_tab",
    ):
        if key in overrides:
            s[key] = str(overrides[key] or "").strip()
    return s
