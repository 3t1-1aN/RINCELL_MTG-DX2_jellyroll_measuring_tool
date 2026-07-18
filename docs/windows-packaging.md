# Windows Packaging

The Rincell tools are Python automations packaged as a local Windows app. Operators should not need to install Python manually for normal use.

## Build Output

The build creates:

- `release/Rincell-Measurement-Tools-<version>/`
- `release/Rincell-Measurement-Tools-<version>.zip`
- `Start Rincell.bat`
- `Rincell Launcher.exe`

The launcher starts the Flask app locally and opens the browser to `http://127.0.0.1:5000/`.

## Recommended: GitHub Release from Linux

You can ship releases without booting Windows. Push a version tag from Linux; GitHub Actions builds on a Windows runner and attaches the zip to a GitHub Release.

```bash
# from the Rincell repo on Linux, after your changes are on main
git checkout main
git pull
git tag v0.1.0
git push origin v0.1.0
```

Then open:

`https://github.com/3t1-1aN/MTG-DX2-data-logger/releases`

Operators download `Rincell-Measurement-Tools-0.1.0.zip` from that release page.

You can also trigger a test build without publishing a release from the Actions tab: **Release Windows App** → **Run workflow**.

## Local Build Steps

Run these commands from PowerShell on a Windows machine if you want a local zip:

```powershell
cd path\to\Rincell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Version 0.1.0
```

The script will:

1. Create `.venv` if needed.
2. Install runtime and build dependencies.
3. Run PyInstaller using `packaging/RincellLauncher.spec`.
4. Copy `.env.example`, `README.md`, and `credentials.json` into the release folder.
5. Create a zip file ready to upload to GitHub Releases or a download website.

## Operator Setup

1. Download the release zip from GitHub Releases.
2. Extract the folder.
3. Double-click `Start Rincell.bat`.
4. Choose the measurement tool.
5. Select the COM port and save settings.
6. Run a test capture.

## Files Operators May Need

- `.env`: created from `.env.example` when settings are saved.
- `credentials.json`: Desktop OAuth client JSON, included in the release zip beside the launcher.
- `token.json`: created automatically after first Google OAuth login (local only; not packaged).

Do not commit or share `token.json` or `.env`.
