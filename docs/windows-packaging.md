# Windows Packaging

The Rincell tools are Python automations packaged as a local Windows app. Operators should not need to install Python manually for normal use.

## Build Output

The build creates:

- `release/Rincell-Measurement-Tools-<version>/`
- `release/Rincell-Measurement-Tools-<version>.zip`
- `Start Rincell.bat`
- `Rincell Launcher.exe`

The launcher starts the Flask app locally and opens the browser to `http://127.0.0.1:5000/`.

## Build Steps

Run these commands from PowerShell on a Windows machine:

```powershell
cd path\to\Rincell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Version 0.1.0
```

The script will:

1. Create `.venv` if needed.
2. Install runtime and build dependencies.
3. Run PyInstaller using `packaging/RincellLauncher.spec`.
4. Copy `.env.example` and `README.md` into the release folder.
5. Create a zip file ready to upload to the download website.

## Operator Setup

1. Download the release zip.
2. Extract the folder.
3. Double-click `Start Rincell.bat`.
4. Choose the measurement tool.
5. Select the COM port and save settings.
6. Run a test capture.

## Files Operators May Need

- `.env`: created from `.env.example` when settings are saved.
- `credentials.json`: Google Sheets credential file, placed beside the launcher.
- `token.json`: created automatically after first Google OAuth login.

Do not commit or upload `credentials.json`, `token.json`, or `.env`.
