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

    def _readline_until_deadline(self, deadline: float) -> str:
        while time.monotonic() < deadline:
            raw = self.ser.readline().decode("utf-8", errors="replace").strip()
            if raw:
                return raw
        raise StepperProtocolError("Timed out waiting for Arduino stepper response.")

    def _wait_for_ready(self) -> StepperPosition:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            line = self._readline_until_deadline(deadline)
            if line.startswith("SCAN_OK"):
                self.push_log(f"INFO|Arduino stepper accepted scan: {line}")
                continue
            if line.startswith("READY "):
                parts = line.split()
                angle = float(parts[2]) if len(parts) > 2 else None
                return StepperPosition(index=int(parts[1]), angle=angle)
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Arduino stepper error: {line}")
            self.push_log(f"INFO|Arduino stepper: {line}")

    def _wait_for_done(self) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            line = self._readline_until_deadline(deadline)
            if line == "DONE":
                return
            if line.startswith("ERR"):
                raise StepperProtocolError(f"Arduino stepper error: {line}")
            self.push_log(f"INFO|Arduino stepper: {line}")
