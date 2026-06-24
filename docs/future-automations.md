# Future Automation Pattern

Future Rincell tools should be added as Python modules behind the local launcher, not as unrelated standalone scripts.

## File Layout

Use this structure:

```text
rincell/
  automations.py
  config.py
  line.py
  web.py
  devices/
    diameter.py
    ohaus.py
    new_device.py
templates/
  launcher.html
  line.html
  index.html
  weight.html
  new_device.html
```

## Add a New Tool

1. Create a device module in `rincell/devices/`.
2. Put serial parsing and device commands in that module.
3. Add settings keys to `rincell/config.py`.
4. Add a web route and API route in `rincell/web.py`.
5. Add a template in `templates/`.
6. Register the tool in `rincell/automations.py`.
7. Add setup/troubleshooting notes to `docs/download-site.md`.
8. Rebuild the Windows release.

## Automation Metadata

Every automation should define:

- `id`: stable machine-readable ID.
- `name`: operator-facing tool name.
- `device`: hardware name.
- `description`: one-sentence outcome.
- `route`: local web route.
- `status`: usually `Ready`, `Beta`, or `Internal`.
- `required_settings`: env/config keys the operator or admin may need.

Example:

```python
AutomationDefinition(
    id="new-device",
    name="New Device Reader",
    device="Device model",
    description="Read measurements from the device and save results.",
    route="/new-device",
    status="Beta",
    required_settings=("NEW_DEVICE_PORT", "NEW_DEVICE_BAUD_RATE"),
)
```

## Design Rules

- Keep device logic independent from Flask routes.
- Keep Google Sheets writes in `rincell/google_sheets.py`.
- Use the production line state pattern when multiple devices contribute to one jellyroll row.
- Keep per-computer settings in `.env`.
- Add UI controls for settings operators must change.
- Prefer one clear capture action per tool.
- Preserve raw device output in results when it helps troubleshooting.
- Avoid hardcoding COM ports or Sheet IDs in code.

## Release Checklist

Before packaging a new automation:

1. Run `python -m compileall app.py launcher.py ohaus_reader.py rincell`.
2. Test the local launcher with `python launcher.py`.
3. Test serial connection on the target Windows PC.
4. Confirm Google Sheets save behavior.
5. Update `docs/download-site.md` with setup/troubleshooting notes.
6. Build with `packaging/build_windows.ps1`.
7. Upload the zip and update release notes on the website.
