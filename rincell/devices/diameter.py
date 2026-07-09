from __future__ import annotations

import time
from typing import Callable

import serial

from .stepper import StepperController

LogFn = Callable[[str], None]


def parse_measurement(raw: str) -> float:
    if ":" in raw:
        return float(raw.split(":")[1])
    return float("".join(c for c in raw if c.isdigit() or c in ".-"))


def to_actual_diameter(dev: float, nominal: float) -> float:
    return nominal + dev


def sample_in_tolerance(actual: float, nominal: float, tolerance: float) -> bool:
    return abs(actual - nominal) <= tolerance


def angle_for_position(index: int, total: int) -> float:
    return round((index - 1) * (360.0 / total), 4)


def evaluate_samples(sample_records: list[dict], nominal: float, tolerance: float) -> dict:
    samples = []
    for sample in sample_records:
        actual = sample["value"]
        dev = actual - nominal
        ok = abs(dev) <= tolerance
        samples.append(
            {
                "index": sample["index"],
                "value": actual,
                "angle": sample.get("angle"),
                "deviation": dev,
                "ok": ok,
            }
        )
    failed = [s for s in samples if not s["ok"]]
    return {
        "tolerance": tolerance,
        "nominal": nominal,
        "samples": samples,
        "pass": len(failed) == 0,
        "failed_count": len(failed),
        "failed_indices": [s["index"] for s in failed],
    }


def capture_one_sample(ser: serial.Serial, settings: dict, sample_index: int, push_log: LogFn) -> float | None:
    total = settings["total_samples"]
    nominal = settings["nominal_diameter"]
    tolerance = settings["tolerance_mm"]
    hw_ref = settings["hw_refresh"]

    ser.reset_input_buffer()
    ser.write(b"R\r\n")
    time.sleep(hw_ref)
    ser.reset_input_buffer()
    ser.write(b"A\r\n")

    raw = ser.readline().decode("utf-8").strip()
    try:
        dev = parse_measurement(raw)
        actual = to_actual_diameter(dev, nominal)
        sign = "+" if dev >= 0 else "-"
        status = "ok" if sample_in_tolerance(actual, nominal, tolerance) else "fail"
        push_log(f"SAMPLE|{sample_index}|{total}|{actual:.4f}|{nominal} {sign} {abs(dev):.4f}|{status}")
        return actual
    except (ValueError, IndexError):
        push_log(f"WARN|Could not parse sample {sample_index}. Raw: '{raw}'")
        return None


def capture_samples(ser: serial.Serial, settings: dict, push_log: LogFn) -> list[dict]:
    sample_records = []
    total = settings["total_samples"]
    hw_ref = settings["hw_refresh"]
    delay = settings["delay_seconds"]

    for i in range(total):
        actual = capture_one_sample(ser, settings, i + 1, push_log)
        if actual is not None:
            sample_records.append({"index": i + 1, "value": actual, "angle": None})

        if i < total - 1:
            time.sleep(max(0, delay - hw_ref))

    return sample_records


def capture_samples_with_motor(
    gauge_ser: serial.Serial,
    motor_ser: serial.Serial,
    settings: dict,
    push_log: LogFn,
    controller: StepperController | None = None,
) -> list[dict]:
    sample_records = []
    total = settings["total_samples"]
    if controller is None:
        controller = StepperController(
            motor_ser,
            push_log,
            timeout_seconds=settings["motor_timeout_seconds"],
        )

    try:
        position = controller.start_scan(total)
        for i in range(total):
            expected = i + 1
            if position.index != expected:
                push_log(f"WARN|Arduino reported stop {position.index}, expected {expected}.")

            actual = capture_one_sample(gauge_ser, settings, expected, push_log)
            if actual is not None:
                angle = position.angle if position.angle is not None else angle_for_position(position.index, total)
                sample_records.append({"index": expected, "value": actual, "angle": angle})

            if i < total - 1:
                position = controller.next_point()

        controller.finish_scan()
    except Exception:
        controller.abort()
        raise

    return sample_records


def capture_diameter(settings: dict, battery_name: str, push_log: LogFn) -> dict | None:
    try:
        motor_port = settings.get("motor_port", "")
        if motor_port and motor_port == settings["port"]:
            push_log("ERROR|Diameter gauge and Arduino motor controller cannot use the same COM port.")
            return None

        with serial.Serial(
            settings["port"],
            settings["baud_rate"],
            timeout=2,
            parity=serial.PARITY_NONE,
        ) as ser:
            if motor_port:
                with serial.Serial(
                    motor_port,
                    settings["motor_baud_rate"],
                    timeout=0.2,
                    parity=serial.PARITY_NONE,
                ) as motor_ser:
                    time.sleep(2.5)
                    controller = StepperController(
                        motor_ser,
                        push_log,
                        timeout_seconds=settings["motor_timeout_seconds"],
                    )
                    controller.wait_for_boot()
                    sample_records = capture_samples_with_motor(
                        ser,
                        motor_ser,
                        settings,
                        push_log,
                        controller=controller,
                    )
            else:
                sample_records = capture_samples(ser, settings, push_log)
    except Exception as exc:
        push_log(f"ERROR|Serial error: {exc}")
        return None

    total = settings["total_samples"]
    if len(sample_records) != total:
        push_log(f"ERROR|Only captured {len(sample_records)}/{total} samples. Aborting.")
        return None

    pts = [sample["value"] for sample in sample_records]
    min_sample = min(sample_records, key=lambda sample: sample["value"])
    max_sample = max(sample_records, key=lambda sample: sample["value"])
    mn = min(pts)
    mx = max(pts)
    tir = mx - mn
    eval_result = evaluate_samples(sample_records, settings["nominal_diameter"], settings["tolerance_mm"])
    result = {
        "points": pts,
        "min": mn,
        "min_angle": min_sample.get("angle"),
        "min_sample_index": min_sample["index"],
        "max": mx,
        "max_angle": max_sample.get("angle"),
        "max_sample_index": max_sample["index"],
        "tir": tir,
        "name": battery_name,
        **eval_result,
    }

    if not eval_result["pass"]:
        details = ", ".join(
            f"S{s['index']} ({s['deviation']:+.4f} mm)"
            for s in eval_result["samples"]
            if not s["ok"]
        )
        push_log(f"WARN|Out of tolerance: {details}")

    return result
