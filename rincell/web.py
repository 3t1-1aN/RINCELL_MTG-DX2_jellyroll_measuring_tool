from __future__ import annotations

import json
import threading
from queue import Queue

import serial.tools.list_ports
from flask import Flask, Response, jsonify, redirect, render_template, request

from .automations import list_automations
from .config import ASSET_DIR, get_settings, save_settings, settings_with_overrides
from .devices.diameter import capture_diameter
from .devices.ohaus import read_once
from .google_sheets import append_diameter_result, append_weight_result, create_or_update_weight_row, update_diameter_row
from .line import LineState, OhausListener

_log_queue: Queue = Queue()
_line_event_queue: Queue = Queue()
_line_state = LineState()


def _is_device_port(port: serial.tools.list_ports.ListPortInfo) -> bool:
    device = port.device or ""
    if port.vid is not None and port.pid is not None:
        return True
    if device.startswith("COM"):
        return True
    return device.startswith(("/dev/ttyUSB", "/dev/ttyACM", "/dev/cu.usb"))


def push_log(msg: str) -> None:
    _log_queue.put(msg)


def push_line_event(event_type: str, payload: dict) -> None:
    _line_event_queue.put({"type": event_type, "payload": payload})


def _handle_ohaus_reading(reading: dict) -> None:
    settings = get_settings()
    armed_id = _line_state.snapshot()["armed_jellyroll_id"]
    if not armed_id:
        _line_state.assign_weight(reading)
        push_line_event("unassigned_weight", {"reading": reading, "state": _line_state.snapshot()})
        return

    row_number = None
    sheet_error = None
    try:
        row_number = create_or_update_weight_row(armed_id, reading, settings)
    except Exception as exc:
        sheet_error = f"Google Sheets weight error: {exc}"

    item = _line_state.assign_weight(reading, row_number=row_number)
    if sheet_error:
        _line_state.mark_error(armed_id, sheet_error)
        push_line_event("line_error", {"jellyroll_id": armed_id, "error": sheet_error, "state": _line_state.snapshot()})
    push_line_event("weight_assigned", {"item": item.to_dict() if item else None, "state": _line_state.snapshot()})


_ohaus_listener = OhausListener(_line_state, _handle_ohaus_reading, push_line_event)


def _run_diameter_capture(battery_name: str, settings: dict) -> None:
    result = capture_diameter(settings, battery_name, push_log)
    if result is None:
        push_log("DONE|")
        return

    push_log(f"RESULT|{json.dumps(result)}")
    try:
        sheet_id = append_diameter_result(battery_name, result, settings)
        push_log(f"SAVED|{sheet_id}")
    except Exception as exc:
        push_log(f"ERROR|Google Sheets error: {exc}")
    push_log("DONE|")


def _run_line_diameter_capture(jellyroll_id: str, settings: dict) -> None:
    item = _line_state.mark_diameter_measuring(jellyroll_id)
    push_line_event("diameter_started", {"jellyroll_id": jellyroll_id, "state": _line_state.snapshot()})

    result = capture_diameter(settings, jellyroll_id, lambda msg: push_line_event("diameter_log", {"message": msg}))
    if result is None:
        _line_state.mark_error(jellyroll_id, "Diameter capture failed.")
        push_line_event("line_error", {"jellyroll_id": jellyroll_id, "error": "Diameter capture failed.", "state": _line_state.snapshot()})
        return

    row_number = item.row_number if item else None
    try:
        row_number = update_diameter_row(jellyroll_id, result, settings, row_number=row_number)
    except Exception as exc:
        _line_state.mark_error(jellyroll_id, f"Google Sheets diameter error: {exc}")
        push_line_event("line_error", {"jellyroll_id": jellyroll_id, "error": str(exc), "state": _line_state.snapshot()})
        return

    completed = _line_state.complete_diameter(jellyroll_id, result, row_number=row_number)
    push_line_event("diameter_complete", {"item": completed.to_dict() if completed else None, "state": _line_state.snapshot()})


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ASSET_DIR / "templates"),
        static_folder=str(ASSET_DIR / "static"),
    )

    @app.route("/")
    def launcher():
        return render_template("launcher.html", automations=list_automations())

    @app.route("/favicon.ico")
    def favicon():
        return redirect("/static/favicon.svg")

    @app.route("/line")
    def line():
        return render_template("line.html")

    @app.route("/diameter")
    def diameter():
        return render_template("index.html")

    @app.route("/weight")
    def weight():
        return render_template("weight.html")

    @app.route("/api/automations")
    def api_automations():
        return jsonify(list_automations())

    @app.route("/api/ports")
    def list_ports():
        ports = [p.device for p in serial.tools.list_ports.comports() if _is_device_port(p)]
        return jsonify(ports)

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        return jsonify(get_settings())

    @app.route("/api/settings", methods=["POST"])
    def api_save_settings():
        save_settings(request.json or {})
        return jsonify({"ok": True})

    @app.route("/api/line/state")
    def api_line_state():
        return jsonify(_line_state.snapshot())

    @app.route("/api/line/weight/arm", methods=["POST"])
    def api_line_arm_weight():
        body = request.json or {}
        jellyroll_id = (body.get("jellyroll_id") or "").strip()
        if not jellyroll_id:
            return jsonify({"error": "Jellyroll ID is required."}), 400
        _line_state.arm_weight(jellyroll_id)
        push_line_event("weight_armed", {"jellyroll_id": jellyroll_id, "state": _line_state.snapshot()})
        return jsonify({"ok": True, "state": _line_state.snapshot()})

    @app.route("/api/line/weight/clear", methods=["POST"])
    def api_line_clear_weight():
        _line_state.clear_arm()
        push_line_event("weight_cleared", {"state": _line_state.snapshot()})
        return jsonify({"ok": True, "state": _line_state.snapshot()})

    @app.route("/api/line/listener/start", methods=["POST"])
    def api_line_listener_start():
        settings = settings_with_overrides(request.json or {})
        if not settings["ohaus_port"]:
            return jsonify({"error": "OHAUS COM port is required."}), 400
        started = _ohaus_listener.start(settings)
        return jsonify({"ok": True, "started": started, "state": _line_state.snapshot()})

    @app.route("/api/line/listener/stop", methods=["POST"])
    def api_line_listener_stop():
        _ohaus_listener.stop()
        return jsonify({"ok": True, "state": _line_state.snapshot()})

    @app.route("/api/line/diameter", methods=["POST"])
    def api_line_diameter():
        body = request.json or {}
        jellyroll_id = (body.get("jellyroll_id") or "").strip()
        if not jellyroll_id:
            return jsonify({"error": "Jellyroll ID is required."}), 400
        settings = settings_with_overrides(body)
        if not settings["port"]:
            return jsonify({"error": "Diameter COM port is required."}), 400
        threading.Thread(target=_run_line_diameter_capture, args=(jellyroll_id, settings), daemon=True).start()
        return jsonify({"ok": True, "state": _line_state.snapshot()})

    @app.route("/api/line/events")
    def api_line_events():
        def generate():
            yield f"data: {json.dumps({'type': 'state', 'payload': _line_state.snapshot()})}\n\n"
            while True:
                event = _line_event_queue.get()
                yield f"data: {json.dumps(event)}\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/api/capture", methods=["POST"])
    @app.route("/api/diameter/capture", methods=["POST"])
    def api_capture():
        body = request.json or {}
        battery_name = (body.get("battery_name") or "").strip()
        if not battery_name:
            return jsonify({"error": "Battery name is required."}), 400

        settings = settings_with_overrides(body)
        if not settings["port"]:
            return jsonify({"error": "COM port is required."}), 400

        threading.Thread(target=_run_diameter_capture, args=(battery_name, settings), daemon=True).start()
        return jsonify({"ok": True})

    @app.route("/api/weight/capture", methods=["POST"])
    def api_weight_capture():
        body = request.json or {}
        sample_name = (body.get("sample_name") or "").strip()
        if not sample_name:
            return jsonify({"error": "Sample name is required."}), 400

        settings = settings_with_overrides(body)
        port = settings["ohaus_port"]
        if not port:
            return jsonify({"error": "OHAUS COM port is required."}), 400

        try:
            reading, raw_lines = read_once(
                port=port,
                baud_rate=settings["ohaus_baud_rate"],
                mode=settings["ohaus_mode"],
                command=settings["ohaus_command"],
                timeout=5.0,
                show_raw=True,
            )
        except Exception as exc:
            return jsonify({"error": f"Serial error: {exc}"}), 500

        if not reading:
            return jsonify({"error": "No valid weight reading received.", "raw_lines": raw_lines}), 408

        reading_data = reading.to_dict()
        saved_sheet_id = None
        if settings["ohaus_sheet_id"]:
            try:
                saved_sheet_id = append_weight_result(sample_name, reading_data, settings)
            except Exception as exc:
                return jsonify({"reading": reading_data, "save_error": str(exc)}), 200

        return jsonify({"reading": reading_data, "sheet_id": saved_sheet_id})

    @app.route("/api/stream")
    def api_stream():
        def generate():
            while True:
                msg = _log_queue.get()
                yield f"data: {msg}\n\n"
                if msg.startswith("DONE|"):
                    break

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
