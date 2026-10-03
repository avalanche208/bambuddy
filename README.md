# Bambuddy Monitor

A monitoring-only fork of [maziggy/bambuddy](https://github.com/maziggy/bambuddy), for printer status and filament inventory. Version **2026.10.3-1d**.

**Developer Mode is not required.** Printers can stay connected to Bambu Cloud while this application reads their local MQTT telemetry. Network and firmware must permit local status access. Nothing in this app starts, pauses, stops, moves, heats, loads, unloads, configures or updates a printer.

This is a deliberately reduced application, not a preference switch in the full Bambuddy UI. It retains upstream's model-aware telemetry parsing and local camera capture, with a new small monitoring interface and database. The full control runtime and UI have been removed. Existing upstream databases are **not imported or modified**; use a separate data directory.

## Kept

- Multi-printer status, progress, layers, remaining time, reported temperatures and HMS alerts.
- AMS/external-spool telemetry: material, color, remaining estimate when reported, humidity and drying status where available.
- Dual-nozzle temperature data and raw reported H2C nozzle-rack details.
- Optional local camera snapshots: RTSPS for H2/P2S/X2D; chamber JPEG for A1/A1 Mini. Images refresh about every ten seconds while the details dialog is open. The app never enables a camera on the printer.
- Local filament inventory: name, brand, material, color, starting/remaining grams, notes, storage location and printer/slot labels. CSV export.
- Observed state history (last 5,000 fleet events) and temperature/progress samples (30 days). Only activity observed while running is recorded.
- Password protection, encrypted stored printer access codes and Docker support.

## Removed

Print sending/reprinting, queues, slicer and virtual-printer integrations, file transfer, archive/model/thumbnail downloads, timelapse retrieval, motion, heaters, fans, lights, AMS configuration/load/unload/RFID refresh, calibration, drying commands/schedules, smart plugs, automatic failure intervention, firmware updating, cloud command integrations and Developer Mode probing/setup requirements. Unrelated project/finance/cloud-library modules are also absent from the reduced UI.

The MQTT client has no actuation methods. Its only outgoing application messages are an exact `pushing.pushall` request and an exact `info.get_version` query; its single publish point rejects every other payload. It subscribes only to the device's report topic. Connection maintenance and camera authentication/stream requests are still necessary to read telemetry/images.

## Printer compatibility

Target models: **H2C, P2S, X2D, A1, A1 Mini, H2D and H2S**. Unknown model names are accepted and standard telemetry is displayed. New hardware, fields or protocols may require parser updates; future compatibility cannot be guaranteed.

See [the research and feature matrix](docs/compatibility.md) for sources, model differences and limitations. Hardware testing against your exact firmware versions is still needed.

## Docker / unRAID

```sh
cp .env.example .env
# Edit .env and choose BAMBUDDY_PASSWORD.
mkdir -p data
sudo chown 1000:1000 data
docker compose pull
docker compose up -d
```

To build locally instead, run `docker compose up -d --build`.

Open `http://SERVER-IP:8000`; sign in as `admin` with the password from `.env`. Add each printer using its local IP, serial number and access code. No Bambu account password is requested.

For unRAID: use `avalanche208/bambuddy:latest`, map container port 8000, keep your existing `/app/data` and `/app/logs` mappings (ownership is set using PUID/PGID, default 1000:1000), and set `BAMBUDDY_PASSWORD`. Change `BAMBUDDY_USERNAME` if desired. The host must reach each printer on TCP 8883; cameras additionally use 322 or 6000. Manual IP setup works with bridge networking; host networking and printer discovery are not required. After validation, pushes to `main` publish `latest` and the application version tag to Docker Hub for amd64 and arm64. This uses the repository secrets `DOCKER_USERNAME` and `DOCKER_PASSWORD` (a Docker Hub access token).

For access beyond a trusted LAN, use your HTTPS reverse proxy. HTTP Basic authentication requires HTTPS to protect the browser-to-server credentials. When using a proxy, preserve the original Host and scheme and configure Uvicorn's trusted proxy IPs appropriately. Printer TLS behavior is inherited from upstream and accepts the printers' self-signed certificates.

Run **one application worker** to avoid duplicate printer connections. Back up the whole `/app/data` directory while the container is stopped, including `credentials.key`; the database alone cannot decrypt printer access codes. Set `.env` permissions appropriately because it contains the app password.

## Native development

Python 3.12+; FFmpeg is needed only for RTSPS snapshots.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export BAMBUDDY_PASSWORD='choose-a-local-password'
python -m uvicorn monitor.main:create_app --factory --host 0.0.0.0 --port 8000 --loop asyncio --workers 1
```

```sh
python -m pytest -q
node --check monitor/static/app.js
```

The CI workflow also builds the Dockerfile. The **Review upstream updates** workflow checks upstream every Sunday at 08:00 UTC and can also be run manually from GitHub Actions. It opens or updates a draft PR with compatible changes to the retained telemetry/camera code, per-file three-way merge results, and a report of other upstream features worth porting. Candidate changes that fail the read-only tests are reverted before the draft PR is created. Conflicts are supplied as review patches, never applied to the running app. Nothing merges or deploys automatically.

See [upstream maintenance](docs/upstream-maintenance.md) for the review process and local commands.

## Provenance and license

Derived from upstream commit `ecddbf2b9294d0118f9d7e2d995b23f07d76b458` (upstream version 1.2.5.7). Copyright and [AGPL-3.0 license](LICENSE) retained. Modifications: read-only protocol boundary, removal of control subsystems, reduced runtime/interface, local inventory, tests and documentation. The app links to this fork’s `monitoring-only` branch for its corresponding source.
