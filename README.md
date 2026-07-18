# Rincell Measurement Tools

Local Windows app for Rincell jellyroll measurements. It talks to USB/serial devices on the operator PC, then writes one Google Sheet row per jellyroll when Sheets is configured.

**Tools**

- **Production Line Workflow** — OHAUS balance + MTG-DX2 diameter gauge (normal shop use)
- **Diagnostic Jellyroll Diameter Tester** — diameter only
- **Diagnostic OHAUS Weight Reader** — weight only

Latest Windows zip: [GitHub Releases](https://github.com/3t1-1aN/RINCELL_MTG-DX2_jellyroll_measuring_tool/releases)

---

## Operator quick start (Windows)

1. Download the latest `Rincell-Measurement-Tools-*.zip` from Releases.
2. Extract the whole folder somewhere permanent (for example `C:\Rincell\`). Do not run it from inside the zip.
3. Open the extracted folder. You should see at least:
   - `Start Rincell.bat`
   - `Rincell Launcher.exe`
   - `credentials.json` (included in the release)
   - `README.md`
   - `.env.example`
4. Double-click `Start Rincell.bat`.
5. If a browser does not open, go to http://127.0.0.1:5000/
6. Open **Production Line Workflow** (or a diagnostic tool).
7. Set COM ports, nominal/target diameter, tolerance, and Google Sheet ID, then **Save**.
8. On the first Google Sheets write, a browser window asks you to sign in. Complete that once. The app creates `token.json` next to the launcher.

After that, day-to-day use is: start the app → start the OHAUS listener → arm jellyroll IDs → weigh → capture diameter.

---

## Important files (keep these together)

All of these live in the **same folder** as `Start Rincell.bat` / `Rincell Launcher.exe`.

| File | What it is | Do I touch it? |
| --- | --- | --- |
| `credentials.json` | Google Desktop OAuth *client* (shipped in the zip) | Leave it. Replace only if Google Cloud client was rotated. |
| `token.json` | *Your* signed-in Google account session | Created automatically. Delete this when login breaks (see below). |
| `.env` | Saved COM ports, diameters, Sheet ID, etc. | Created/updated when you click Save in the UI. |
| `.env.example` | Template of settings keys | Reference only. |

**Do not move** `credentials.json` into `_internal\`, Desktop, or Downloads by itself. The app only looks beside the launcher.

**Do not share** `.env` or `token.json`. Sharing `credentials.json` outside the company release package is also a bad idea.

---

## Web UI guide

Every tool runs in the browser at http://127.0.0.1:5000/. Use **Home** / the RINCELL header link to return to the launcher.

### Launcher (`/`)

Home page with one card per tool:

| On screen | What it means |
| --- | --- |
| Status badge (`Primary` / `Diagnostic`) | Primary = normal production. Diagnostic = setup / troubleshooting only. |
| Tool name + device line | Which hardware that tool uses. |
| Description | Short purpose of the page. |
| Settings Used chips | Env keys that tool cares about (set them in the tool UI, not here). |
| **Open Tool** | Opens that tool’s page. |

### Production Line Workflow (`/line`) — normal shop use

Two station columns, then queues below.

**Weight Station – OHAUS Listener**

| Control | Purpose |
| --- | --- |
| Jellyroll ID + **Arm Next Weight** | Bind the next OHAUS reading to this ID (Enter also arms). |
| Armed badge | Shows which ID is waiting for a weight. |
| Listener badge | Whether the serial listener is running. |
| OHAUS COM Port / Baud / Mode | Balance connection. Mode `listen` waits for Auto Print or PRINT. |
| **Start Listener** / **Stop Listener** | Begin or stop watching the balance. |
| Weight log | Live serial / assignment messages. |

There is no separate “capture weight” button in normal line mode — the armed ID + a balance print creates the Sheet row.

**Diameter Station – Gauge Capture**

| Control | Purpose |
| --- | --- |
| Diameter Gauge COM Port | MTG-DX2 serial port. |
| Arduino Motor COM Port | Optional stepper that rotates the part between radius samples. |
| Gauge / motor baud rates | Serial speeds for those devices. |
| Radius Samples | Must be even (default 12). Opposite radii are stitched into diameters. |
| Stepper Timeout (s) | How long to wait for motor moves. |
| Nominal Diameter (mm) | Calibration master diameter. Used to turn gauge deviation into actual size. |
| Target Diameter (mm) | Pass/fail center. Can differ from nominal. |
| Tolerance (± mm) | Allowed distance from target. |
| Google Sheet ID / Sheet Tab | Where rows are written (`Tab` blank = first tab). |
| **Save Settings** | Writes these values to `.env` beside the launcher. |

**Queues**

| Section | Purpose |
| --- | --- |
| Jellyrolls Waiting for Diameter | Weighed IDs ready for gauge capture. Each card has **Capture Diameter**. |
| Completed This Session | Finished this app run. Cleared if you restart the app (Sheet rows remain). |

Status bar at the top shows pass/fail and error messages for the current action.

### Jellyroll Diameter Tester (`/diameter`) — diagnostic

Single-station diameter page for setup and troubleshooting (no OHAUS queue).

| Area | Purpose |
| --- | --- |
| Left **Device Settings** | Gauge COM, baud, optional motor COM/baud, radius samples, delay between samples, HW refresh, Sheet ID/tab, **Save Settings**. |
| **Test Parameters** | Nominal diameter, target diameter, tolerance. |
| Battery / sample name + **Capture** | Name for this run, then starts a full diameter capture. |
| Live log | Step-by-step capture messages. |
| Results card | Pass/fail badge, Min / Max / Avg / TIR, polar viz, per-sample grid, link to the Sheet when configured. |

### OHAUS Weight Reader (`/weight`) — diagnostic

Weight-only page (no diameter queue).

| Control | Purpose |
| --- | --- |
| OHAUS COM / Baud / Read Mode | Balance connection. `listen` = wait for print; `poll` = send a command. |
| Poll Command | Used in poll mode (default `IP`). |
| Sheet ID / Tab | Optional logging (`OHAUS_*` settings). Blank Sheet ID = do not save. |
| Sample name + **Capture Weight** | One-shot weight read for that name. |
| Reading card | Weight value, unit/stability meta, and raw serial line. |

### Diameter polar viz (line + diameter pages)

After a diameter capture, the chart shows **radius** points (not stitched diameters as the outline):

| Legend item | Meaning |
| --- | --- |
| Target R | Target radius (= target diameter ÷ 2), bold ring. |
| ± tolerance (R) | Pass band in radius units (half the diameter tolerance). |
| Max Ø radii | The two opposite radius points that form the largest stitched diameter (green). |
| Min Ø radii | The two opposite radius points that form the smallest stitched diameter (red). |
| TIR | Max diameter − min diameter from stitching. |
| Rings | Concentric 0.1 mm radius steps for scale. |

Blue points are other in-tolerance radii. Out-of-tolerance radii fail the sample set even if min/max look fine.

---

## Google Sheets login and expired access

### First login

1. Make sure `credentials.json` is beside `Start Rincell.bat`.
2. Enter a valid **Google Sheet ID** in the app and Save.
3. Run a capture that writes to Sheets (weight or diameter).
4. Sign in in the browser and allow Sheets access.
5. `token.json` appears beside the launcher. Leave it there.

### When Google login stops working

Usually the refresh token expired, the account password changed, access was revoked, or the wrong Google account was used.

**Fix (most common):**

1. Close the app.
2. In the launcher folder, **delete `token.json` only**.
3. Keep `credentials.json` and `.env`.
4. Start the app again and trigger a Sheets write.
5. Complete the browser login again. A new `token.json` is created.

The app also tries to refresh tokens automatically. If refresh fails, it deletes `token.json` and opens the browser login itself. If that loop fails or you still see Sheets errors, delete `token.json` manually as above.

### If `credentials.json` is missing

Copy it from a fresh release zip into the launcher folder (same place as `Start Rincell.bat`), then delete `token.json` and sign in again.

### Sheet permissions

The Google account you sign in with must be able to edit the target spreadsheet. Wrong Sheet ID, wrong tab name, or view-only access will still fail even with a good `token.json`.

---

## Production line workflow

1. Open **Production Line Workflow**.
2. Confirm OHAUS COM port, diameter COM port, Sheet ID, nominal diameter, target diameter, and tolerance. Save.
3. Start the OHAUS listener.
4. Enter or scan the jellyroll ID and arm it.
5. Place that jellyroll on the OHAUS balance (Auto Print or PRINT).
6. Move it to the diameter gauge.
7. Click **Capture Diameter** for that queued jellyroll.

Weight creates the Sheet row. Diameter updates the same row. Restarting the app clears the in-memory queue; rows already written to Sheets stay.

More detail: `docs/production-line-workflow.md`.

---

## Measurement model

The gauge reports deviation from the calibration master (**nominal diameter**):

`actual = nominal + gauge_value`

Pass/fail uses a separate **target diameter**:

`pass when |actual − target| ≤ tolerance`

Example: calibrate on a 17.5 mm master (`nominal = 17.5`) while judging product at `17.3 ± 0.05` (`target = 17.3`, `tolerance = 0.05`).

Diameter capture uses an even number of radius samples (default 12) and stitches opposite radii into diameters.

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| App will not start / bat closes immediately | Extract the full folder; run `Start Rincell.bat` from that folder; try `Rincell Launcher.exe` directly; check antivirus quarantine. |
| Browser does not open | Open http://127.0.0.1:5000/ manually. |
| No COM ports listed | Cable, device power, USB driver; unplug/replug; click refresh ports. |
| Serial / port busy | Close other software using that COM port (including a second Rincell window). |
| OHAUS no weight | Listener running? Correct OHAUS COM? Auto Print enabled or press PRINT? Jellyroll ID armed? |
| Unassigned OHAUS reading | Arm the jellyroll ID before weighing. |
| Diameter capture fails / odd count error | Use an even sample count (2, 4, 6, …). Check gauge COM, baud, and timing. |
| `Missing: ...\credentials.json` | Put release `credentials.json` beside `Start Rincell.bat`. |
| Google login / refresh / Sheets auth errors | Delete `token.json`, keep `credentials.json`, sign in again. |
| Sheets permission / not found errors | Check Sheet ID, tab name, and that the signed-in account can edit the sheet. |
| Settings keep resetting | Confirm you clicked Save; confirm `.env` exists beside the launcher and the folder is writable. |

---

## Developer / source install (optional)

Only needed if you are changing code, not for normal operators.

```bash
pip install -r requirements.txt
cp .env.example .env   # or copy manually on Windows
```

Place a Desktop OAuth `credentials.json` in the repo root (same level as `launcher.py`).

```bash
python launcher.py
```

Legacy / CLI helpers:

```bash
python app.py
python ohaus_reader.py --list-ports
python ohaus_reader.py --port COM5 --mode listen
```

---

## Building a new Windows release

From a machine with git access, after changes are on `main`:

```bash
git tag v0.2.2
git push origin v0.2.2
```

GitHub Actions builds the zip and publishes a Release. The zip must include `credentials.json` beside the launcher (`packaging/build_windows.ps1` fails if that file is missing).

Details: `docs/windows-packaging.md`. Website outline: `docs/download-site.md`.
