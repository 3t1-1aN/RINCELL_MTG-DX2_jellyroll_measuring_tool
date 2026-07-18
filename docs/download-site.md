# Rincell Download Website

The website should distribute the packaged Windows app and help operators recover from common setup problems. It should not run the serial-device automations directly.

## Page Map

### Home / Download

Purpose: get an operator to the correct installer quickly.

Content:

- Product name: Rincell Measurement Tools.
- Primary button: Download latest Windows release.
- Current version and release date.
- Supported tools:
  - Production Line Workflow.
  - Diagnostic Jellyroll Diameter Tester.
  - Diagnostic OHAUS Weight Reader.
- Basic requirements:
  - Windows PC.
  - USB/serial cable for the device.
  - Release zip already includes `credentials.json` for Google Sheets OAuth.

### Setup Guide

Purpose: first-run checklist.

Content:

1. Download and extract the release zip (keep all files in one folder).
2. Confirm `credentials.json` is beside `Start Rincell.bat`.
3. Double-click `Start Rincell.bat`.
4. Select `Production Line Workflow` from the launcher.
5. Connect the OHAUS balance and diameter gauge.
6. Pick COM ports, nominal/target diameter, tolerance, and Google Sheet ID. Save.
7. Start the OHAUS listener.
8. On first Sheets write, complete the browser Google login (`token.json` is created).
9. Arm a jellyroll ID, capture weight, then capture diameter from the queue.

Include screenshots for:

- Launcher home page.
- Production Line Workflow page (weight station, diameter station, waiting queue).
- Diameter settings panel (nominal vs target).
- OHAUS settings panel.
- Successful capture result and polar viz legend.

Component-by-component UI meanings are documented in the root `README.md` under **Web UI guide**.

### Device Guides

Purpose: device-specific operating instructions.

Diameter guide:

- Supported device: MTG-DX2 diameter gauge.
- Serial settings: COM port, baud rate, sample count, hardware refresh, delay.
- Measurement model: actual diameter = nominal (calibration) diameter + gauge deviation.
- Pass/fail: against target diameter ± tolerance (target may differ from nominal).
- Output: min, max, TIR, tolerance status, failed samples.

OHAUS guide:

- Supported device: OHAUS Explorer balance.
- Modes:
  - Listen: wait for Auto Print or operator PRINT.
  - Poll: send command such as `IP`.
- Output: weight, unit, stability, mode, raw serial line.

Production line guide:

- Enter or scan jellyroll ID before placing the jellyroll on the balance.
- OHAUS output is passive; no web UI button is needed for normal weight capture.
- Diameter capture is triggered from the queued jellyroll card.
- One Google Sheet row is used per jellyroll.

### Troubleshooting

Purpose: fast recovery for common shop-floor issues.

Common issues:

- No COM ports found: check cable, driver, device power, and refresh ports.
- Wrong COM port: unplug/replug device and compare the port list.
- Serial error: close other software that may already be using the device.
- OHAUS no reading: enable Auto Print, press PRINT, or switch to poll mode.
- Unassigned OHAUS reading: enter/scan and arm a jellyroll ID before weighing.
- Diameter capture incomplete: confirm gauge command support, baud rate, and sample timing.
- Google Sheets auth error: delete `token.json` beside the launcher, keep `credentials.json`, retry and sign in again.
- Google Sheets permission / not found: check Sheet ID, tab name, and that the signed-in account can edit the sheet.
- Missing credentials: copy `credentials.json` from a fresh release zip into the launcher folder.

### Release Notes

Purpose: make updates understandable and auditable.

Each release should include:

- Version.
- Date.
- Download link.
- Added tools.
- Fixed device issues.
- Config changes.
- Known limitations.

### Admin / Developer Notes

Purpose: help a future developer add automations consistently.

Link to:

- `docs/windows-packaging.md`.
- `docs/production-line-workflow.md`.
- `docs/future-automations.md`.
- GitHub or internal source repository.
