# Fork maintenance

Upstream baseline: maziggy/bambuddy v1.2.5.7, ecddbf2b9294d0118f9d7e2d995b23f07d76b458.

Preserve the original complete application, UI, authentication, database, features and paths. The UI customization removes the persistent Developer LAN Mode warning banner and its polling query from frontend/src/components/Layout.tsx. Update its layout regression test accordingly. Diagnostic tools and actual printer limitations remain unchanged.

Docker Compose points at avalanche208/bambuddy. The fork publishing workflow tests the layout and builds the original Dockerfile for amd64/arm64, then publishes latest and the application version. Increment APP_VERSION in backend/app/core/config.py for each fork publication.

The discarded monitoring-only rewrite must not be reintroduced. Its monitor.db is separate from upstream bambuddy.db; no existing database is deleted or overwritten by this restoration. Data entered only in that discarded interface is not automatically imported.

Weekly release maintenance preserves these small changes while merging official stable releases, validates before promotion, and checks publishing success.

The automatic Developer Mode ams_filament_setting probe is disabled in bambu_mqtt.py. Preserve passive mode detection and normal user-initiated controls; do not suppress real HMS faults.

UI release 1h: PrinterCardPreview adds a browser-local per-printer live/preview toggle using CameraTile and 20% larger preview dimensions. Update checks use UPDATE_GITHUB_REPO=avalanche208/bambuddy, preserving original upstream attribution. Fork suffixes are compared by date/revision; the publishing workflow creates a GitHub release only after a successful Docker push. Rollback image before these features: 1.2.5.7-fork.2026.10.3.1g.
