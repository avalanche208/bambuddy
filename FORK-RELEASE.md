Prevent additional unsolicited calibration requests after printer boot/reconnection when Developer Mode is disabled or unknown. The earlier MQTT connection fix missed application-level calibration priming and automatic restoration of saved K-profiles after power cycles.

Guard background calibration priming, restoration/retries, AMS-change calibration selection, deferred SpoolBuddy configuration, and backup calibration queries. Manual controls and deliberate queued printing remain unchanged. Real HMS faults remain visible; this update does not clear printer faults. Calibration K-values may be unavailable until the printer reports them.

Keep the original interface, enlarged live-preview toggle, authentication, database, /app/data and /app/logs unchanged.

Image: avalanche208/bambuddy:1.2.5.7-fork.2026.10.3.1j (also latest).
Rollback: avalanche208/bambuddy:1.2.5.7-fork.2026.10.3.1i.
