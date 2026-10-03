# Fork maintenance

Upstream baseline: maziggy/bambuddy v1.2.5.7, ecddbf2b9294d0118f9d7e2d995b23f07d76b458.

Preserve the original complete application, UI, authentication, database, features and paths. The UI customization removes the persistent Developer LAN Mode warning banner and its polling query from frontend/src/components/Layout.tsx. Update its layout regression test accordingly. Diagnostic tools and actual printer limitations remain unchanged.

Docker Compose points at avalanche208/bambuddy. The fork publishing workflow tests the layout and builds the original Dockerfile for amd64/arm64, then publishes latest and the application version. Increment APP_VERSION in backend/app/core/config.py for each fork publication.

The discarded monitoring-only rewrite must not be reintroduced. Its monitor.db is separate from upstream bambuddy.db; no existing database is deleted or overwritten by this restoration. Data entered only in that discarded interface is not automatically imported.

Weekly release maintenance preserves these small changes while merging official stable releases, validates before promotion, and checks publishing success.

The automatic Developer Mode ams_filament_setting probe is disabled in bambu_mqtt.py. Preserve passive mode detection and normal user-initiated controls; do not suppress real HMS faults.

UI release 1h: PrinterCardPreview adds a browser-local per-printer live/preview toggle using CameraTile and 20% larger preview dimensions. Update checks use UPDATE_GITHUB_REPO=avalanche208/bambuddy, preserving original upstream attribution. Fork suffixes are compared by date/revision; the publishing workflow creates a GitHub release only after a successful Docker push. Rollback image before these features: 1.2.5.7-fork.2026.10.3.1g.

Release 1i: the MQTT connection callback sends only pushall and get_version; its automatic K-profile priming is disabled (explicit K-profile retrieval remains available). This did not cover application-level callbacks, corrected in 1j. Keep real HMS faults visible, including retained printer-side faults. Enlarge inline preview to 9rem on desktop and 7.2rem on mobile, with matching status area height.

Release 1j: require passively reported developer_mode is True before background calibration-table priming, idle/power-cycle K-profile restoration, AMS inlet/spool-change calibration selection, deferred SpoolBuddy slot configuration, and backup K-profile queries. Unknown and False both skip these commands. Recheck the idle restoration guard at execution time; deliberate queued-print dispatch remains unchanged. Preserve these guards on upstream sync. Do not hide actual HMS errors. Monitoring may lack K-values until supplied by printer reports. No UI, deployment-path, authentication, or database changes.
