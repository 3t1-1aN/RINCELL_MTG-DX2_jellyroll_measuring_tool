# Windows Packaging

The Rincell tools are Python automations packaged as a local Windows app. Operators should not need to install Python for normal use.

Operator handoff instructions live in the root `README.md`. This file is for building and shipping releases.

## Build Output

The build creates:

- `release/Rincell-Measurement-Tools-<version>/`
- `release/Rincell-Measurement-Tools-<version>.zip`

Inside the folder:

- `Start Rincell.bat`
- `Rincell Launcher.exe`
- `credentials.json` (required; copied from the repo root)
- `README.md`
- `.env.example`

The launcher starts the Flask app locally and opens http://127.0.0.1:5000/.

## Recommended: GitHub Release from Linux

Push a version tag from Linux; GitHub Actions builds on a Windows runner and attaches the zip to a GitHub Release.

```bash
# from the Rincell repo on Linux, after your changes are on main
git checkout main
git pull
git tag v0.2.2
git push origin v0.2.2
```

Release page:

https://github.com/3t1-1aN/RINCELL_MTG-DX2_jellyroll_measuring_tool/releases

You can also trigger a test build without publishing a release from the Actions tab: **Release Windows App** → **Run workflow**.

## Local Build Steps

Run from PowerShell on a Windows machine if you want a local zip:

```powershell
cd path\to\Rincell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Version 0.2.2
```

The script will:

1. Create `.venv` if needed.
2. Install runtime and build dependencies.
3. Run PyInstaller using `packaging/RincellLauncher.spec`.
4. Copy `.env.example`, `README.md`, and `credentials.json` into the release folder.
5. Fail if `credentials.json` is missing from the repo root.
6. Create a zip ready for GitHub Releases.

## Operator Setup (short)

Full handoff steps are in `README.md`. Short version:

1. Download the release zip from GitHub Releases.
2. Extract the folder.
3. Confirm `credentials.json` is beside `Start Rincell.bat`.
4. Double-click `Start Rincell.bat`.
5. Save COM ports, diameters, and Sheet ID in the UI.
6. On first Sheets write, complete browser login (`token.json` is created locally).

## Auth files

| File | Packaged? | Notes |
| --- | --- | --- |
| `credentials.json` | Yes | Desktop OAuth client beside the launcher. |
| `token.json` | No | Created after operator login. Delete it to force re-login. |
| `.env` | No | Created when settings are saved in the UI. |

Do not commit or share `token.json` or `.env`.
