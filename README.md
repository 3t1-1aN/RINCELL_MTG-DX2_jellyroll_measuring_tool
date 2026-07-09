# Rincell Measurement Tools

Local Windows-friendly automation tools for Rincell jellyroll measurements. The app runs on the operator's computer so it can talk to USB/serial devices, then saves one Google Sheet row per jellyroll when configured.

Current tools:

- Production Line Workflow for the OHAUS balance and MTG-DX2 diameter gauge.
- Diagnostic Jellyroll Diameter Tester for the MTG-DX2 gauge.
- Diagnostic OHAUS Weight Reader for the OHAUS Explorer balance.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your settings.

3. Add Google credentials:
   - Place a Desktop OAuth `credentials.json` or service account JSON in this folder.
   - On first run, the app opens a browser to authorize Google Sheets access and writes `token.json`.

## Run the launcher

```bash
python launcher.py
```

Open http://localhost:5000 if the browser does not open automatically.

The launcher has cards for each measurement tool.

## Production line workflow

Use the `Production Line Workflow` card for normal operation.

1. Start the OHAUS listener.
2. Enter or scan the jellyroll ID and arm it for the next weight.
3. Place the jellyroll on the OHAUS balance.
4. Let the balance auto-output a stable reading, or press PRINT on the balance.
5. Move the jellyroll to the diameter gauge.
6. Capture diameter for that queued jellyroll.

The app writes the raw OHAUS weight output first, then updates the same Google Sheet row with min diameter and angle, max diameter and angle, TIR, tolerance status, and overall status.

## Run the legacy diameter entry point

```bash
python app.py
```

Open http://localhost:5000/diameter

## Run the OHAUS CLI reader

```bash
python ohaus_reader.py --list-ports
python ohaus_reader.py --port COM5 --mode listen
```

## Measurement model

The gauge reports deviation from nominal. Actual diameter is:

`actual = BATTERY_NOMINAL_DIAMETER_MM + captured_value`

Positive values add to nominal; negative values subtract.

## Windows packaging / GitHub Releases

Preferred path from Linux: push a version tag and let GitHub Actions build the Windows zip.

```bash
git tag v0.1.0
git push origin v0.1.0
```

Operators download the zip from the repo Releases page.

Local Windows build (optional):

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Version 0.1.0
```

See `docs/windows-packaging.md` for the release process and `docs/download-site.md` for the website/download portal outline.
