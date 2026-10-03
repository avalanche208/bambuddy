# Keeping the monitoring fork current

Upstream is `maziggy/bambuddy`; your fork is `avalanche208/bambuddy`. Preserve the upstream history and remote. Avoid GitHub's unconditional “Sync fork” merge button: the full upstream application contains controls intentionally removed here.

## Weekly and manual review

`Review upstream updates` runs every Sunday at 08:00 UTC (3 AM CDT / 2 AM CST), or on demand in GitHub Actions. Scheduled workflows must exist on the default branch. GitHub may pause schedules on inactive public repositories, so check the Actions page if no review appears.

The workflow fetches the official main branch and compares it with `UPSTREAM.json`. Only explicitly listed telemetry, camera and supporting files are eligible for automatic three-way merge preparation. It retains this fork's edits where Git can merge them, and leaves conflicting files unchanged. Candidate source changes must pass the read-only/API tests; if validation fails, all candidate source changes are restored before opening the PR. Upstream diffs remain in `docs/upstream-review/*.patch` for manual inspection, never in executable paths.

The workflow opens/updates a **draft** pull request on `review/upstream-monitor`. It also reports changed files outside the allowlist, so new upstream features can be considered without silently restoring the full control application. No PR is merged and no image is deployed automatically. Allow GitHub Actions to create pull requests under Settings → Actions → General if the repository's default token settings prevent it.

An automated compatibility test cannot prove all firmware behavior. Review the diff, recheck the outgoing MQTT boundary, inspect the source and Docker results in `checks.txt`, test affected hardware, then merge. New modules, UI functionality or storage-dependent features require an intentional port into `monitor/`. Never resolve conflicts by replacing the trimmed MQTT client with upstream's full client.

`UPSTREAM.json` stores a baseline per file. Baselines advance only for successfully prepared changes; conflicted/rejected files keep their old baseline. After manually accepting a port, set that file's baseline to the upstream commit reviewed. The review watermark tracks discovery of new upstream features separately from acceptance of code. Successful automated source proposals receive a new date/commit-based application version; manual ports should also change `monitor/__init__.py`.

## Local process

```sh
git switch main
git pull --ff-only origin main
git remote add upstream https://github.com/maziggy/bambuddy.git # once only
git fetch upstream main
git switch -c review-upstream
python scripts/sync_upstream.py --upstream-ref upstream/main
python -m pytest -q
node --check monitor/static/app.js
docker build -t bambuddy-monitor:review .
```

Commit the proposal and open a PR into your own fork. The script requires a clean starting checkout so it cannot overwrite unrelated local edits. If a PR reports only patches, no source changes were accepted automatically. The maintenance mechanism supports future feature ports; it does not promise every feature can work without Developer Mode.
