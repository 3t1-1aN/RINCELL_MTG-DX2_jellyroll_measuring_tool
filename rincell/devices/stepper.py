from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

import serial

LogFn = Callable[[str], None]


class StepperProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class StepperPosition:
    index: int
    angle: float | None = None


class StepperController:
    def __init__(self, ser: serial.Serial, push_log: LogFn, timeout_seconds: float = 10.0) -> None:
        self.ser = ser
        self.push_log = push_log
        self.timeout_seconds = timeout_seconds

    def wait_for_boot(self, boot_timeout_seconds: float = 4.0) -> None:
        """Drain ESP32/Arduino boot text and confirm the motor firmware is alive."""
        deadline = time.monotonic() + boot_timeout_seconds
        while time.monotonic() < deadline:
            line = self._try_readline_until_deadline(deadline)
            if not line:
                break
            if line in {"MOTOR_READY", "PONG"}:
                return
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Motor controller error during boot: {line}")

        self._write("PING")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            line = self._try_readline_until_deadline(deadline)
            if not line:
                break
            if line == "PONG":
                return
            if line.startswith("ERR"):
                break

        self._write("ABORT")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            line = self._try_readline_until_deadline(deadline)
            if not line:
                break
            if line == "ABORTED":
                return
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Motor controller error during ABORT: {line}")

        raise StepperProtocolError(
            "Motor controller did not respond after boot. "
            "Check the motor COM port, 9600 baud, and that Rincell firmware is flashed "
            "with USB CDC On Boot enabled."
        )

    def start_scan(self, total_points: int) -> StepperPosition:
        self.ser.reset_input_buffer()
        self._write(f"SCAN {total_points}")
        return self._wait_for_ready()

    def next_point(self) -> StepperPosition:
        self._write("NEXT")
        return self._wait_for_ready()

    def finish_scan(self) -> None:
        self._write("NEXT")
        self._wait_for_done()

    def abort(self) -> None:
        try:
            self._write("ABORT")
        except serial.SerialException:
            return

    def _write(self, command: str) -> None:
        self.ser.write(f"{command}\n".encode("utf-8"))
        self.ser.flush()

    def _try_readline_until_deadline(self, deadline: float) -> str | None:
        while time.monotonic() < deadline:
            raw = self.ser.readline().decode("utf-8", errors="replace").strip()
            if raw:
                return raw
        return None

    def _readline_until_deadline(self, deadline: float) -> str:
        line = self._try_readline_until_deadline(deadline)
        if line:
            return line
        raise StepperProtocolError("Timed out waiting for motor controller response.")

    def _wait_for_ready(self) -> StepperPosition:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            line = self._readline_until_deadline(deadline)
            if line.startswith("SCAN_OK"):
                continue
            if line.startswith("READY "):
                parts = line.split()
                angle = float(parts[2]) if len(parts) > 2 else None
                return StepperPosition(index=int(parts[1]), angle=angle)
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Arduino stepper error: {line}")

    def _wait_for_done(self) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            line = self._readline_until_deadline(deadline)
            if line == "DONE":
                return
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Arduino stepper error: {line}")
