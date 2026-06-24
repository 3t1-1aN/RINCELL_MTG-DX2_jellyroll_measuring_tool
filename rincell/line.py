from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable

from .devices.ohaus import open_serial, parse_line, send_command


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class LineItem:
    jellyroll_id: str
    status: str
    created_at: str = field(default_factory=now_stamp)
    updated_at: str = field(default_factory=now_stamp)
    weight_reading: dict | None = None
    diameter_result: dict | None = None
    row_number: int | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class LineState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.armed_jellyroll_id: str | None = None
        self.pending: list[LineItem] = []
        self.completed: list[LineItem] = []
        self.unassigned_reading: dict | None = None
        self.listener: dict = {
            "running": False,
            "port": None,
            "last_error": None,
            "last_reading_at": None,
        }

    def arm_weight(self, jellyroll_id: str) -> None:
        with self._lock:
            self.armed_jellyroll_id = jellyroll_id

    def clear_arm(self) -> None:
        with self._lock:
            self.armed_jellyroll_id = None

    def assign_weight(self, reading: dict, row_number: int | None = None) -> LineItem | None:
        with self._lock:
            if not self.armed_jellyroll_id:
                self.unassigned_reading = reading
                return None

            jellyroll_id = self.armed_jellyroll_id
            item = self._find_item(jellyroll_id)
            if item is None:
                item = LineItem(jellyroll_id=jellyroll_id, status="waiting_diameter")
                self.pending.append(item)

            item.weight_reading = reading
            item.row_number = row_number
            item.status = "waiting_diameter"
            item.updated_at = now_stamp()
            item.error = None
            self.armed_jellyroll_id = None
            self.listener["last_reading_at"] = item.updated_at
            return item

    def mark_diameter_measuring(self, jellyroll_id: str) -> LineItem | None:
        with self._lock:
            item = self._find_pending(jellyroll_id)
            if item:
                item.status = "measuring_diameter"
                item.updated_at = now_stamp()
            return item

    def complete_diameter(self, jellyroll_id: str, result: dict, row_number: int | None = None) -> LineItem | None:
        with self._lock:
            item = self._find_pending(jellyroll_id)
            if item is None:
                item = LineItem(jellyroll_id=jellyroll_id, status="complete")

            item.diameter_result = result
            if row_number is not None:
                item.row_number = row_number
            item.status = "complete" if result.get("pass") else "check_diameter"
            item.updated_at = now_stamp()
            item.error = None

            self.pending = [p for p in self.pending if p.jellyroll_id != jellyroll_id]
            self.completed.insert(0, item)
            self.completed = self.completed[:25]
            return item

    def mark_error(self, jellyroll_id: str, error: str) -> None:
        with self._lock:
            item = self._find_item(jellyroll_id)
            if item:
                item.status = "error"
                item.error = error
                item.updated_at = now_stamp()

    def set_listener_status(self, **updates) -> None:
        with self._lock:
            self.listener.update(updates)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "armed_jellyroll_id": self.armed_jellyroll_id,
                "pending": [item.to_dict() for item in self.pending],
                "completed": [item.to_dict() for item in self.completed],
                "unassigned_reading": self.unassigned_reading,
                "listener": dict(self.listener),
            }

    def _find_item(self, jellyroll_id: str) -> LineItem | None:
        return self._find_pending(jellyroll_id) or next(
            (item for item in self.completed if item.jellyroll_id == jellyroll_id),
            None,
        )

    def _find_pending(self, jellyroll_id: str) -> LineItem | None:
        return next((item for item in self.pending if item.jellyroll_id == jellyroll_id), None)


class OhausListener:
    def __init__(
        self,
        state: LineState,
        on_reading: Callable[[dict], None],
        on_event: Callable[[str, dict], None],
    ) -> None:
        self.state = state
        self.on_reading = on_reading
        self.on_event = on_event
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self, settings: dict) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(dict(settings),), daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self, settings: dict) -> None:
        port = settings["ohaus_port"]
        baud_rate = settings["ohaus_baud_rate"]
        mode = settings.get("ohaus_mode", "listen")
        command = settings.get("ohaus_command", "IP")
        interval = float(settings.get("ohaus_interval", 1.0))

        self.state.set_listener_status(running=True, port=port, last_error=None)
        self.on_event("listener", {"running": True, "port": port})

        try:
            with open_serial(port, baud_rate) as ser:
                next_poll = 0.0
                while not self._stop.is_set():
                    if mode == "poll" and time.time() >= next_poll:
                        send_command(ser, command)
                        next_poll = time.time() + max(0.2, interval)

                    raw = ser.readline()
                    if not raw:
                        continue

                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    reading = parse_line(line)
                    if reading:
                        reading_data = reading.to_dict()
                        self.on_reading(reading_data)
                    else:
                        self.on_event("raw", {"raw": line})
        except Exception as exc:
            self.state.set_listener_status(running=False, last_error=str(exc))
            self.on_event("listener_error", {"error": str(exc)})
            return

        self.state.set_listener_status(running=False)
        self.on_event("listener", {"running": False, "port": port})
