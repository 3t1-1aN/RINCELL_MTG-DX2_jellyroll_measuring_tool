# Production Line Workflow

The production workflow runs the OHAUS weight station and diameter gauge station side by side.

## Operator Flow

1. Open the Rincell launcher.
2. Select `Production Line Workflow`.
3. Confirm the OHAUS COM port, diameter gauge COM port, nominal/target diameter, tolerance, and Google Sheet settings.
4. Start the OHAUS listener.
5. Enter or scan the next jellyroll ID.
6. Place that jellyroll on the OHAUS balance.
7. Wait for Auto Print output or press PRINT on the balance.
8. Move the jellyroll to the diameter gauge.
9. Click `Capture Diameter` for that jellyroll in the waiting queue.

While the diameter gauge is measuring one jellyroll, the next jellyroll can already be armed and weighed.

## Google Sheet Model

The production workflow uses one row per test. If the same jellyroll ID is tested again, the app appends a new row instead of replacing the previous one.

Columns include:

- Jellyroll ID.
- Weight timestamp and raw OHAUS output.
- Diameter timestamp.
- Min diameter with angle, max diameter with angle, average diameter, TIR, tolerance, and diameter status.
- Overall status.

Pass/fail uses target diameter ± tolerance. Nominal diameter is the calibration master only.

Weight capture creates the row. Diameter capture updates that same test row.

## OHAUS Behavior

The web UI does not need a weight capture button during normal operation.

The app listens to the OHAUS serial output. A weight is accepted when:

- The balance auto-outputs a stable measurement.
- The operator presses PRINT on the balance.
- The line station has a jellyroll ID armed.

If the OHAUS sends a valid reading while no jellyroll ID is armed, the app shows it as unassigned and does not write it to Google Sheets automatically.

## Diameter Behavior

The diameter gauge remains operator-triggered.

The first version uses a web UI button for `Capture Diameter`. A keyboard shortcut, such as Space, can be added later once the station layout and scanner behavior are confirmed.

## Important Assumption

This first version assumes one station PC controls both devices. The in-progress queue is in memory, so restarting the app clears the visible queue. Completed data already written to Google Sheets remains in the sheet.
