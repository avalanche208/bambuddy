Fix status-handler test failures by treating missing Developer Mode information as unknown. Background calibration remains disabled unless the printer positively reports Developer Mode enabled.

Correct the update-version test import formatting. Docker publication now requires the full CI workflow to pass for the same commit, including all backend test shards and lint checks.

No interface, database, authentication, or deployment-path changes.

Image: avalanche208/bambuddy:1.2.5.7-fork.2026.10.3.1k (also latest).
Rollback: avalanche208/bambuddy:1.2.5.7-fork.2026.10.3.1j.
