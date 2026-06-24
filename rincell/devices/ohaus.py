from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime

import serial
import serial.tools.list_ports

WEIGHT_LINE_RE = re.compile(
    r"^\s*(?P<weight>[+-]?\d+(?:\.\d+)?)\s+"
    r"(?P<unit>g|kg|lb(?:\s*:\s*oz)?|oz|t|c)\b",
    re.IGNORECASE,
)

SKIP_PREFIXES = (
    "MODE:",
    "PV",
    "VERSION",
    "H ",
    "INFO",
)


@dataclass(frozen=True)
class WeightReading:
    raw: str
    weight: float
    unit: str
    stable: bool
    mode: str | None
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def list_serial_ports() -> list[str]:
    return [port.device for port in serial.tools.list_ports.comports()]


def detect_mode(suffix: str) -> str | None:
    text = suffix.replace("?", "").strip().upper()
    if not text:
        return None
    if "NET" in text or text == "N":
        return "N"
    if "TARE" in text or text == "T":
        return "T"
    if "GROSS" in text or text == "G":
        return "G"
    return None


def parse_line(line: str) -> WeightReading | None:
    text = line.strip()
    if not text:
        return None

    upper = text.upper()
    if upper.startswith(SKIP_PREFIXES):
        return None

    match = WEIGHT_LINE_RE.match(text)
    if not match:
        return None

    weight = float(match.group("weight"))
    unit = match.group("unit").replace(" ", "").lower()
    if unit == "lb:oz":
        unit = "lb:oz"

    suffix = text[match.end() :]
    stable = "?" not in suffix
    mode = detect_mode(suffix)

    return WeightReading(
        raw=text,
        weight=weight,
        unit=unit,
        stable=stable,
        mode=mode,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def format_reading(reading: WeightReading, show_raw: bool = False) -> str:
    parts = [
        reading.timestamp,
        f"{reading.weight:.4f} {reading.unit}",
        "stable" if reading.stable else "unstable",
    ]
    if reading.mode:
        parts.append(reading.mode)
    line = " | ".join(parts)
    if show_raw:
        line += f" | raw={reading.raw!r}"
    return line


def open_serial(port: str, baud_rate: int) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baud_rate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,
    )


def send_command(ser: serial.Serial, command: str) -> None:
    ser.reset_input_buffer()
    ser.write(f"{command}\r\n".encode("ascii"))
    ser.flush()


def read_until_reading(ser: serial.Serial, timeout: float, show_raw: bool = False) -> tuple[WeightReading | None, list[str]]:
    deadline = time.time() + timeout
    raw_lines: list[str] = []
    while time.time() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        if show_raw:
            raw_lines.append(line)
        reading = parse_line(line)
        if reading:
            return reading, raw_lines
    return None, raw_lines


def read_once(
    port: str,
    baud_rate: int,
    mode: str = "listen",
    command: str = "IP",
    timeout: float = 5.0,
    show_raw: bool = False,
) -> tuple[WeightReading | None, list[str]]:
    with open_serial(port, baud_rate) as ser:
        if mode == "poll":
            send_command(ser, command)
            time.sleep(0.15)
        return read_until_reading(ser, timeout=timeout, show_raw=show_raw)
