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


def nominal_radius(nominal_diameter: float) -> float:
    return nominal_diameter / 2.0


def to_actual_radius(dev: float, nominal_diameter: float) -> float:
    return nominal_radius(nominal_diameter) + dev


def diameter_sample_count(radius_count: int) -> int:
    return radius_count // 2


def require_even_radius_count(total: int) -> None:
    if total < 2 or total % 2 != 0:
        raise ValueError(f"Radius sample count must be an even number >= 2 (got {total}).")


def sample_in_tolerance(actual: float, target: float, tolerance: float) -> bool:
    return abs(actual - target) <= tolerance


def angle_for_position(index: int, total: int) -> float:
    return round((index - 1) * (360.0 / total), 4)


def stitch_opposite_radii_to_diameters(radius_records: list[dict]) -> list[dict]:
    """Pair each radius with the opposite-angle reading to form diameter measurements."""
    pair_count = len(radius_records) // 2
    diameters: list[dict] = []
    for i in range(pair_count):
        first = radius_records[i]
        opposite = radius_records[i + pair_count]
        diameters.append(
            {
                "index": i + 1,
                "value": first["value"] + opposite["value"],
                "angle": first.get("angle"),
                "radius_indices": (first["index"], opposite["index"]),
                "radius_angles": (first.get("angle"), opposite.get("angle")),
            }
        )
    return diameters


def evaluate_samples(
    sample_records: list[dict],
    target: float,
    tolerance: float,
    *,
    nominal: float | None = None,
) -> dict:
    """Judge samples against target ± tolerance. Nominal is calibration reference only."""
    samples = []
    for sample in sample_records:
        actual = sample["value"]
        dev = actual - target
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
        "target": target,
        "nominal": nominal if nominal is not None else target,
        "samples": samples,
        "pass": len(failed) == 0,
        "failed_count": len(failed),
        "failed_indices": [s["index"] for s in failed],
    }


def capture_one_radius_sample(
    ser: serial.Serial,
    settings: dict,
    sample_index: int,
    push_log: LogFn,
) -> float | None:
    total = settings["total_samples"]
    nominal_diameter = settings["nominal_diameter"]
    target_radius = nominal_radius(nominal_diameter)
    hw_ref = settings["hw_refresh"]

    ser.reset_input_buffer()
    ser.write(b"R\r\n")
    time.sleep(hw_ref)
    ser.reset_input_buffer()
    ser.write(b"A\r\n")

    raw = ser.readline().decode("utf-8").strip()
    try:
        dev = parse_measurement(raw)
        actual_radius = to_actual_radius(dev, nominal_diameter)
        sign = "+" if dev >= 0 else "-"
        push_log(
            f"RADIUS|{sample_index}|{total}|{actual_radius:.4f}|"
            f"{target_radius:.4f} {sign} {abs(dev):.4f}"
        )
        return actual_radius
    except (ValueError, IndexError):
        push_log(f"WARN|Could not parse radius sample {sample_index}. Raw: '{raw}'")
        return None


def log_stitched_diameters(
    diameter_records: list[dict],
    target: float,
    tolerance: float,
    push_log: LogFn,
) -> None:
    total = len(diameter_records)
    for sample in diameter_records:
        actual = sample["value"]
        dev = actual - target
        sign = "+" if dev >= 0 else "-"
        status = "ok" if sample_in_tolerance(actual, target, tolerance) else "fail"
        push_log(
            f"DIAMETER|{sample['index']}|{total}|{actual:.4f}|"
            f"{target} {sign} {abs(dev):.4f}|{status}"
        )


def capture_radius_samples(ser: serial.Serial, settings: dict, push_log: LogFn) -> list[dict]:
    sample_records = []
    total = settings["total_samples"]
    hw_ref = settings["hw_refresh"]
    delay = settings["delay_seconds"]

    for i in range(total):
        actual_radius = capture_one_radius_sample(ser, settings, i + 1, push_log)
        if actual_radius is not None:
            sample_records.append({"index": i + 1, "value": actual_radius, "angle": None})

        if i < total - 1:
            time.sleep(max(0, delay - hw_ref))

    return sample_records


def capture_radius_samples_with_motor(
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

            actual_radius = capture_one_radius_sample(gauge_ser, settings, expected, push_log)
            if actual_radius is not None:
                angle = position.angle if position.angle is not None else angle_for_position(position.index, total)
                sample_records.append({"index": expected, "value": actual_radius, "angle": angle})

            if i < total - 1:
                position = controller.next_point()

        controller.finish_scan()
    except Exception:
        controller.abort()
        raise

    return sample_records


def capture_diameter(settings: dict, battery_name: str, push_log: LogFn) -> dict | None:
    total = settings["total_samples"]
    try:
        require_even_radius_count(total)
    except ValueError as exc:
        push_log(f"ERROR|{exc}")
        return None

    diameter_count = diameter_sample_count(total)
    push_log(
        f"INFO|Capturing {total} radius points -> {diameter_count} stitched diameters."
    )

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
                    radius_records = capture_radius_samples_with_motor(
                        ser,
                        motor_ser,
                        settings,
                        push_log,
                        controller=controller,
                    )
            else:
                radius_records = capture_radius_samples(ser, settings, push_log)
    except Exception as exc:
        push_log(f"ERROR|Serial error: {exc}")
        return None

    if len(radius_records) != total:
        push_log(f"ERROR|Only captured {len(radius_records)}/{total} radius samples. Aborting.")
        return None

    diameter_records = stitch_opposite_radii_to_diameters(radius_records)
    nominal = settings["nominal_diameter"]
    target = settings["target_diameter"]
    tolerance = settings["tolerance_mm"]
    log_stitched_diameters(diameter_records, target, tolerance, push_log)

    pts = [sample["value"] for sample in diameter_records]
    min_sample = min(diameter_records, key=lambda sample: sample["value"])
    max_sample = max(diameter_records, key=lambda sample: sample["value"])
    mn = min(pts)
    mx = max(pts)
    avg = sum(pts) / len(pts)
    tir = mx - mn
    eval_result = evaluate_samples(diameter_records, target, tolerance, nominal=nominal)
    result = {
        "points": pts,
        "radius_samples": radius_records,
        "radius_sample_count": total,
        "diameter_count": diameter_count,
        "min": mn,
        "min_angle": min_sample.get("angle"),
        "min_sample_index": min_sample["index"],
        "max": mx,
        "max_angle": max_sample.get("angle"),
        "max_sample_index": max_sample["index"],
        "avg": avg,
        "tir": tir,
        "name": battery_name,
        **eval_result,
    }

    if not eval_result["pass"]:
        details = ", ".join(
            f"D{s['index']} ({s['deviation']:+.4f} mm)"
            for s in eval_result["samples"]
            if not s["ok"]
        )
        push_log(f"WARN|Out of tolerance: {details}")

    return result
