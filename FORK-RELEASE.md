Update to official Bambuddy v1.3.0, released November 7, 2026. Includes multi-print archives, inventory improvements, camera updates, permission fixes and upstream database migrations.

Preserve fork update checks, the remembered enlarged live preview, removed Developer LAN banner, and passive-only guards on background calibration. New finish-photo bed movements require positively reported Developer Mode. Manual controls and queued-print dispatch remain available. Docker paths and volumes are unchanged.

Read upstream upgrade notes before deployment: https://github.com/maziggy/bambuddy/releases/tag/v1.3.0

Candidate image: avalanche208/bambuddy:1.3.0-fork.2026.11.8.1 (not published until validation succeeds).
Previous image: avalanche208/bambuddy:1.2.5.7-fork.2026.10.3.1k. Preserve a pre-upgrade database backup for rollback across upstream database migrations.
