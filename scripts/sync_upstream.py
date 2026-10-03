#!/usr/bin/env python3
"""Prepare a reviewable upstream update; never merge or publish it automatically."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True)


def merge_versions(ours, base, theirs):
    """Return merged text, or None for a conflict. Never write conflict markers."""
    with tempfile.TemporaryDirectory() as directory:
        files = [Path(directory) / name for name in ('ours', 'base', 'theirs')]
        for path, content in zip(files, (ours, base, theirs)):
            path.write_text(content)
        result = subprocess.run(['git', 'merge-file', '-p', *map(str, files)], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        if result.returncode == 1:
            return None
        raise RuntimeError(result.stderr or 'Three-way merge failed')


def validate_candidate(repo):
    checks = ([sys.executable, '-m', 'pytest', '-q'], ['node', '--check', 'monitor/static/app.js'])
    results = []
    passed = True
    for command in checks:
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        passed = passed and result.returncode == 0
        results.append('$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
    return passed, '\n'.join(results)


def prepare_updates(repo, upstream_ref):
    repo = Path(repo)
    manifest_path = repo / 'UPSTREAM.json'
    manifest = json.loads(manifest_path.read_text())
    upstream_sha = git(repo, 'rev-parse', '--verify', upstream_ref + '^{commit}').strip()
    old_review = manifest['reviewed_commit']
    updates, conflicts, original, baselines = [], [], {}, dict(manifest['files'])
    for filename, base_sha in manifest['files'].items():
        destination = repo / filename
        base = git(repo, 'show', f'{base_sha}:{filename}')
        try:
            theirs = git(repo, 'show', f'{upstream_sha}:{filename}')
        except subprocess.CalledProcessError:
            conflicts.append(filename + ' (deleted upstream; kept locally)')
            continue
        ours = destination.read_text()
        if base == theirs:
            continue
        merged = merge_versions(ours, base, theirs)
        if merged is None:
            conflicts.append(filename)
            continue
        original[filename] = ours
        destination.write_text(merged)
        baselines[filename] = upstream_sha
        updates.append(filename)

    if upstream_sha == old_review and not updates and not conflicts:
        return False

    passed, test_output = validate_candidate(repo) if updates else (True, 'No source candidates to validate.')
    if not passed:
        # Restore only the exact files this invocation changed. Keep the report
        # and proposed upstream patches separate from executable application code.
        for filename, content in original.items():
            (repo / filename).write_text(content)
        baselines = dict(manifest['files'])

    outside = git(repo, 'diff', '--name-only', old_review, upstream_sha).splitlines()
    outside = [name for name in outside if name not in manifest['files']]
    commits = git(repo, 'log', '--format=%h %s', '--max-count=40', f'{old_review}..{upstream_sha}')
    folder = repo / 'docs' / 'upstream-review'
    folder.mkdir(parents=True, exist_ok=True)
    # Deterministic review output means an unchanged upstream does not create
    # a new weekly PR. Old proposals stay in git history.
    for path in folder.glob('*.patch'):
        path.unlink()
    for filename in [*updates, *[c.split(' (')[0] for c in conflicts]]:
        patch = git(repo, 'diff', manifest['files'][filename], upstream_sha, '--', filename)
        if len(patch.encode()) <= 1_000_000:
            (folder / (filename.replace('/', '__') + '.patch')).write_text(patch)
    (folder / 'checks.txt').write_text(test_output)
    report = [
        '# Upstream review', '',
        f'Upstream: [{upstream_sha}](https://github.com/maziggy/bambuddy/commit/{upstream_sha})', '',
        'This is a draft proposal. Nothing is merged or deployed automatically.', '',
        '## Retained source changes', '',
        ('Candidate source changes passed the monitoring-only tests.' if passed else
         'Candidate validation FAILED. All candidate source changes were restored; this PR contains review material only.'), '',
        *[f'- `{name}`' for name in updates], '',
        '## Conflicts requiring manual porting', '',
        *([f'- `{name}`' for name in conflicts] or ['None.']), '',
        '## Other upstream changes', '',
        'These files are outside the read-only allowlist. Review the upstream diff for useful features and port them into the monitoring runtime deliberately.', '',
        *([f'- `{name}`' for name in outside[:200]] or ['None.']), '',
        ('Additional changed files omitted; see the full upstream compare.' if len(outside) > 200 else ''), '',
        '## Recent upstream commits', '', '```text', commits.rstrip(), '```', '',
        'Before merging: inspect every change, confirm no printer control or mode requirement returned, run the Docker build, and update the version. Conflict files retain their previous per-file baseline until their port is accepted.', '',
    ]
    (folder / 'README.md').write_text('\n'.join(report))
    manifest['reviewed_commit'] = upstream_sha
    manifest['files'] = baselines
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    if passed and updates:
        version_path = repo / 'monitor' / '__init__.py'
        date = datetime.datetime.now(datetime.timezone.utc)
        version = f'{date.year}.{date.month}.{date.day}-u{upstream_sha[:7]}'
        lines = version_path.read_text().splitlines()
        version_path.write_text('\n'.join(f'__version__ = "{version}"' if line.startswith('__version__') else line for line in lines) + '\n')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-ref', default='upstream/main')
    args = parser.parse_args()
    repo = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').strip())
    if git(repo, 'status', '--porcelain').strip():
        raise SystemExit('Start from a clean working tree; commit or stash local changes first.')
    print('Prepared upstream review.' if prepare_updates(repo, args.upstream_ref) else 'Already reviewed this upstream revision.')


if __name__ == '__main__':
    main()
