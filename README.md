# MTG-DX2 Data Logger

Web UI and CLI tools for capturing battery diameter measurements from an MTG-DX2 gauge over serial, converting gauge deviations to actual diameters, and logging results to Google Sheets.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your settings.

3. Add Google credentials:
   - Place a Desktop OAuth `credentials.json` or service account JSON in this folder.
   - On first run, the app opens a browser to authorize Google Sheets access and writes `token.json`.

## Run the web app

```bash
python app.py
```

Open http://localhost:5000

## Run the CLI logger

```bash
python data_logger.py
```

## Measurement model

The gauge reports deviation from nominal. Actual diameter is:

`actual = BATTERY_NOMINAL_DIAMETER_MM + captured_value`

Positive values add to nominal; negative values subtract.
