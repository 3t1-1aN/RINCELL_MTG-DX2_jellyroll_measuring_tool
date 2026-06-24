from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationDefinition:
    id: str
    name: str
    device: str
    description: str
    route: str
    status: str
    required_settings: tuple[str, ...]


AUTOMATIONS: tuple[AutomationDefinition, ...] = (
    AutomationDefinition(
        id="production-line",
        name="Production Line Workflow",
        device="OHAUS balance + MTG-DX2 diameter gauge",
        description="Run weight and diameter stations side by side, using one Google Sheet row per jellyroll.",
        route="/line",
        status="Primary",
        required_settings=("OHAUS_PORT", "PORT", "GOOGLE_SHEET_ID", "GOOGLE_SHEET_TAB"),
    ),
    AutomationDefinition(
        id="jellyroll-diameter",
        name="Jellyroll Diameter Tester",
        device="MTG-DX2 diameter gauge",
        description="Diagnostic/manual diameter-only capture for setup and troubleshooting.",
        route="/diameter",
        status="Diagnostic",
        required_settings=("PORT", "BAUD_RATE", "BATTERY_NOMINAL_DIAMETER_MM", "DIAMETER_TOLERANCE_MM", "GOOGLE_SHEET_ID"),
    ),
    AutomationDefinition(
        id="ohaus-weight",
        name="OHAUS Weight Reader",
        device="OHAUS Explorer balance",
        description="Diagnostic/manual OHAUS reader for setup and troubleshooting.",
        route="/weight",
        status="Diagnostic",
        required_settings=("OHAUS_PORT", "OHAUS_BAUD_RATE", "OHAUS_MODE", "OHAUS_GOOGLE_SHEET_ID"),
    ),
)


def list_automations() -> list[dict]:
    return [automation.__dict__ for automation in AUTOMATIONS]
