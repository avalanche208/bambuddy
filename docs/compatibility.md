# Non-Developer-Mode compatibility research

Research date: October 3, 2026 (October 2 evening in America/Chicago). Requested fleet: H2C, P2S, X2D, A1, A1 Mini, H2D, H2S, and future models. Exact firmware versions were not supplied. This is a documentation and source-code assessment, **not physical-printer certification**.

## Main finding

Developer Mode is a control-access issue, not a universal requirement for reading printer status. Bambu Lab's authorization announcement explicitly excludes outgoing status reports from its new authorization checks. It restricts critical actions including print initiation, motion, temperatures, fans, AMS configuration and calibration. Its follow-up describes Developer Mode as an optional way to open local channels. [1][2]

The maintained Home Assistant integration independently documents that sensor reads survive the authorization firmware changes and that local MQTT can coexist with Bambu Cloud. LAN-only operation and Developer Mode are separate choices. You do not need to disable Bambu Handy/cloud connectivity merely because this fork connects to the printer's local MQTT broker. [3]

This fork does not bypass authorization, impersonate Bambu Connect, install certificates on the printer, downgrade firmware or sign control commands. It requests a status snapshot and firmware information, then consumes reports.

## Feature decisions

| Feature | Without Developer Mode | Fork behavior |
| --- | --- | --- |
| Print state, progress, layers, remaining time, temperatures, HMS | Read-only reports remain available; actual fields vary | Keep reported readings |
| AMS material, color, active equipment data and remaining estimate | Available when firmware/AMS reports them | Keep; unknown stays unknown |
| AMS humidity, temperature, drying countdown/status | Sensor/equipment dependent; AMS Lite differs from enclosed AMS | Display received data only |
| External spool information | Configured type/color may be reported; no reliable universal remaining-grams field | Keep reported information |
| Local inventory | No printer access required | Keep local records and manual gram updates |
| Printer/slot assignment | A local association is safe; configuring the actual AMS is a write | Local labels only; no AMS command |
| Exact per-print filament usage | Usually needs additional print metadata, rather than status alone | No automatic gram deduction; do not invent precision |
| Camera | Local feed can work, sometimes with a separate local-liveview toggle | Optional snapshots; no camera-setting commands |
| Print-file/thumbnail/timelapse download | Can work in some setups, but varies with FTP access and storage | Removed from this focused app; not claimed universally blocked |
| Start/reprint/pause/resume/stop, skip objects | Control operations | Removed even if older firmware accepts them |
| Motion, temperatures, fans, LEDs, calibration | Writes; some LED exceptions exist but are outside scope | Removed, including exceptions |
| AMS load/unload, RFID refresh, filament profiles, drying control | Printer/AMS writes | Removed |
| Queues, virtual printer, slicer dispatch, smart plugs, automation | Can actuate hardware directly or indirectly | Removed |
| Firmware update and Bambu cloud command paths | Not monitoring | Removed |
| Full archive, model previews, projects, finance | Outside this small monitoring app or dependent on removed file workflows | Removed |

The HA project's entity list distinguishes basic status/AMS data from print weight, length and cover imagery that need credentials or a retrieved print file. This is why the fork keeps printer-reported estimates separate from manually maintained inventory grams. Humidity indices are not mislabeled as percentages. Missing or unsupported readings are not zero-weight or empty-spool assertions. [5]

## Model assessment

| Model | Telemetry path retained | Camera path retained | Specific limits |
| --- | --- | --- | --- |
| H2C | Local MQTT; upstream H2C/rack parsing | RTSPS, TCP 322 | Rack data only when reported; no hotend selection or AMS writes |
| H2D | Local MQTT; dual-extruder parsing | RTSPS, TCP 322 | Separate local-liveview setting may be needed; no tool/laser/cutter controls |
| H2S | Local MQTT | RTSPS, TCP 322 | Local-liveview permission may be needed |
| P2S | Local MQTT | RTSPS, TCP 322 | Treat camera access as firmware-dependent; file metadata can depend on external storage |
| X2D | Local MQTT; existing upstream model parsing | RTSPS, TCP 322 | Local-liveview permission may be needed; newer firmware still needs field verification |
| A1 | Local MQTT | TLS chamber JPEG, TCP 6000 | No chamber-temperature or enclosed-AMS humidity assumptions |
| A1 Mini | Local MQTT | TLS chamber JPEG, TCP 6000 | Low-frame-rate/availability behavior varies; absent data stays unknown |
| Future models | Generic existing report fields | User selects protocol or leaves camera off | New encoding, authentication, ports or fields require future work |

Camera protocols/model mapping are taken from Bambuddy's retained `backend/app/services/camera.py` at the pinned upstream commit. The HA setup guide specifically documents H2D/H2S/X2D local liveview without enabling LAN-only operation. This is evidence for keeping optional local viewing, **not a guarantee for every listed firmware**. [4]

The same guide documents that H2D 01.03.00.00, H2S 01.02.00.00 and P2S can require external media plus “Store Sent Files on External Storage” for file-derived sensors. That distinction makes a universal “no Developer Mode means no FTP” claim inaccurate. This fork deliberately avoids those dependencies. [4]

## Upstream audit and changes

Upstream initialization started a print scheduler, smart-plug scheduling, camera/detection automation and virtual-printer services. Its MQTT client contained many direct publish sites. Its Developer Mode probe sent `ams_filament_setting` to an external slot; it was not a passive test. Filament assignment also published AMS settings/calibration information. Hiding UI buttons alone would have left background write paths.

Those runtimes, routes and UI modules are removed from the working tree. The retained MQTT parser has a single outgoing publish point accepting only exact `pushall` and `get_version` payload shapes. Arbitrary command publishing, raw forwarding and all actuation methods are deleted. Only the report topic is subscribed. No control framework is loaded alongside the monitor.

To make removal practical and reviewable, this is a new reduced interface/runtime built around upstream telemetry and camera code, rather than the full upstream UI with permissions hiding unwanted controls. It uses a separate `monitor.db`; it is not an in-place replacement that migrates every Bambuddy feature or database.

## Validation and remaining evidence gaps

Automated tests cover absent control endpoints/methods, strict outgoing payload validation, initial connection traffic, the requested model names plus an unknown model, partial AMS reports, credentials, inventory persistence, camera caching, stale readings and API authentication. Model-name parameterization checks code behavior; it is not equivalent to a captured real telemetry fixture for each model. Desktop/mobile browser checks are recorded separately in `validation.md`.

Before relying on any individual printer, verify that status arrives with Developer Mode off, check slot/material/color against its display, and test its optional camera separately. A missing camera must not be treated as a reason to enable Developer Mode. Observe a real print to verify field interpretation and disconnect the network briefly to verify stale indication. Exact grams and unobserved historical prints are intentionally not inferred.

## Sources

1. Bambu Lab, [Firmware Update Introducing New Authorization Control System](https://blog.bambulab.com/firmware-update-introducing-new-authorization-control-system-2/) (January 16, 2025; updated January 20).
2. Bambu Lab, [Updates and Third-Party Integration with Bambu Connect](https://blog.bambulab.com/updates-and-third-party-integration-with-bambu-connect/) (January 20, 2025).
3. Maintainer documentation, [ha-bambulab integration overview](https://github.com/greghesp/ha-bambulab/blob/main/docs/index.mdx).
4. Maintainer documentation, [ha-bambulab setup](https://github.com/greghesp/ha-bambulab/blob/main/docs/setup.mdx).
5. Maintainer documentation, [ha-bambulab entities](https://docs.page/greghesp/ha-bambulab/entities).
6. Bambuddy, [Getting Started](https://wiki.bambuddy.cool/getting-started/) and [upstream repository](https://github.com/maziggy/bambuddy). These distinguish read-only access from full-control requirements; some other Bambuddy pages make broader Developer Mode claims, so the feature-level manufacturer/maintainer evidence above takes precedence.
7. Pinned source audit: [MQTT client](https://github.com/maziggy/bambuddy/blob/ecddbf2b9294d0118f9d7e2d995b23f07d76b458/backend/app/services/bambu_mqtt.py), [startup/runtime](https://github.com/maziggy/bambuddy/blob/ecddbf2b9294d0118f9d7e2d995b23f07d76b458/backend/app/main.py), [filament assignment](https://github.com/maziggy/bambuddy/blob/ecddbf2b9294d0118f9d7e2d995b23f07d76b458/backend/app/api/routes/inventory.py), [camera protocols](https://github.com/maziggy/bambuddy/blob/ecddbf2b9294d0118f9d7e2d995b23f07d76b458/backend/app/services/camera.py).
