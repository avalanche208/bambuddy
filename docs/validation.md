# Validation record — 2026.10.3-1a

- 33 backend tests passed with Python 3.12 and the pinned runtime dependencies.
- Control API paths return 404. Control methods and the Developer Mode probe are absent.
- Initial MQTT connection subscribes only to `device/<serial>/report` and sends only `pushall` plus `get_version`.
- Mixed/extra-field command payloads are rejected at the sole MQTT publish point.
- Tested partial AMS updates, all seven requested model names plus an unknown model, stale status, missing chamber sensors, history and removal/reconnect callback boundaries.
- Tested password protection, encrypted credential storage, secret redaction from responses, validation, cross-origin mutation rejection, inventory persistence/deletion and CSV formula escaping.
- Tested optional camera caching and camera-failure behavior with mocked capture; no live printer camera was reachable from this environment.
- Headless Chromium: added a printer and a spool through the real UI, opened history, checked a 1440-pixel desktop viewport and 390-pixel mobile viewport. No JavaScript errors or horizontal overflow. Desktop and mobile screenshots visually inspected.
- Python compilation, JavaScript syntax and installed dependency consistency checks passed.

## Not verified here

No physical printers, model-specific firmware versions or real credentials were supplied. Synthetic model-name tests do not certify each firmware's payload or camera. No actual print, heater, motion, AMS control or firmware update was performed. Docker is unavailable in this workspace, so the image was not built locally; the included GitHub Actions workflow builds it after publication. No Docker registry image has been published.

This fork uses a new `monitor.db`, not upstream's database schema. No upstream data migration is implemented. Inventory gram balances are manually maintained; printer telemetry percentages do not silently overwrite them.
