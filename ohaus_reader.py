#!/usr/bin/env python3
"""Read weight measurements from an OHAUS Explorer balance over serial."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import serial
from serial import SerialException

from rincell.config import get_settings
from rincell.devices.ohaus import format_reading, list_serial_ports, open_serial, parse_line, send_command

_settings = get_settings()
DEFAULT_PORT = _settings["ohaus_port"]
DEFAULT_BAUD = _settings["ohaus_baud_rate"]


def read_stream(ser: serial.Serial, show_raw: bool) -> None:
    print("Listening for balance output. Press Ctrl+C to stop.")
    print("Tip: enable Auto Print or press PRINT on the balance to send readings.\n")

    while True:
        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        if show_raw:
            print(f"RAW: {line!r}")

        reading = parse_line(line)
        if reading:
            print(format_reading(reading, show_raw=show_raw))
        elif show_raw:
            print(f"SKIP: {line!r}")


def read_on_demand(ser: serial.Serial, command: str, interval: float, show_raw: bool) -> None:
    print(f"Requesting readings with '{command}' every {interval:.1f}s. Press Ctrl+C to stop.\n")

    while True:
        send_command(ser, command)
        time.sleep(0.15)

        deadline = time.time() + 1.0
        got_reading = False
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            if show_raw:
                print(f"RAW: {line!r}")

            reading = parse_line(line)
            if reading:
                print(format_reading(reading, show_raw=show_raw))
                got_reading = True
                break

        if not got_reading:
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} | no reading received")

        time.sleep(max(0.0, interval))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read OHAUS Explorer weight measurements over serial.",
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Baud rate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List available serial ports and exit",
    )
    parser.add_argument(
        "--mode",
        choices=("listen", "poll"),
        default="listen",
        help="listen: passively read balance output; poll: send IP command on an interval",
    )
    parser.add_argument(
        "--command",
        default="IP",
        help="Serial command to request a reading in poll mode (default: IP)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between poll requests (default: 1.0)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw serial lines for debugging",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.list_ports:
        ports = list_serial_ports()
        if not ports:
            print("No serial ports found.")
            return 0
        print("Available serial ports:")
        for port in ports:
            print(f"  {port}")
        return 0

    try:
        with open_serial(args.port, args.baud) as ser:
            print(f"Connected to {args.port} @ {args.baud} baud")
            if args.mode == "listen":
                read_stream(ser, show_raw=args.raw)
            else:
                read_on_demand(ser, args.command, args.interval, show_raw=args.raw)
    except SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        if "Permission denied" in str(exc) and sys.platform.startswith("linux"):
            print(
                "Linux tip: add your user to the dialout group, then log out and back in:\n"
                "  sudo usermod -aG dialout $USER",
                file=sys.stderr,
            )
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
