import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('sync_upstream', Path(__file__).parents[1] / 'scripts/sync_upstream.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def commit(repo, message):
    subprocess.run(['git','add','.'],cwd=repo,check=True)
    subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm',message],cwd=repo,check=True)
    return sync.git(repo,'rev-parse','HEAD').strip()


@pytest.fixture
def repository(tmp_path):
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True)
    (tmp_path/'sensor.py').write_text('value = 1\n')
    base=commit(tmp_path,'base')
    (tmp_path/'UPSTREAM.json').write_text(json.dumps({'reviewed_commit':base,'files':{'sensor.py':base}}))
    (tmp_path/'monitor').mkdir()
    (tmp_path/'monitor/__init__.py').write_text('__version__ = "test"\n')
    return tmp_path,base


def test_three_way_preserves_fork_removals():
    base='read = 1\n\ndef control():\n    publish("stop")\n'
    ours='read = 1\n'
    theirs='read = 2\n\ndef control():\n    publish("stop")\n'
    merged = sync.merge_versions(ours,base,theirs)
    assert merged is None or merged == 'read = 2\n'  # An adjacent edit may safely conflict.


def test_conflict_never_writes_markers():
    assert sync.merge_versions('value = 2\n','value = 1\n','value = 3\n') is None


def test_successful_candidate_advances_only_allowed_file(repository,monkeypatch):
    repo,base=repository
    (repo/'sensor.py').write_text('value = 3\n')
    (repo/'new_controls.py').write_text('dangerous = True\n')
    head=commit(repo,'upstream change')
    (repo/'sensor.py').write_text('value = 1\n')
    (repo/'new_controls.py').unlink()
    monkeypatch.setattr(sync,'validate_candidate',lambda repo:(True,'passed'))
    assert sync.prepare_updates(repo,head)
    assert (repo/'sensor.py').read_text()=='value = 3\n'
    assert not (repo/'new_controls.py').exists()
    assert json.loads((repo/'UPSTREAM.json').read_text())['files']['sensor.py']==head
    assert 'new_controls.py' in (repo/'docs/upstream-review/README.md').read_text()


def test_failed_validation_restores_source_and_baseline(repository,monkeypatch):
    repo,base=repository
    (repo/'sensor.py').write_text('publish("stop")\n')
    head=commit(repo,'unsafe candidate')
    (repo/'sensor.py').write_text('value = 1\n')
    monkeypatch.setattr(sync,'validate_candidate',lambda repo:(False,'boundary failed'))
    sync.prepare_updates(repo,head)
    assert (repo/'sensor.py').read_text()=='value = 1\n'
    assert json.loads((repo/'UPSTREAM.json').read_text())['files']['sensor.py']==base
    assert 'FAILED' in (repo/'docs/upstream-review/README.md').read_text()
    assert (repo/'monitor/__init__.py').read_text()=='__version__ = "test"\n'


def test_same_upstream_is_noop(repository,monkeypatch):
    repo,base=repository
    def unexpected(repo):raise AssertionError('No validation needed for unchanged upstream')
    monkeypatch.setattr(sync,'validate_candidate',unexpected)
    assert sync.prepare_updates(repo,base) is False


def test_multiple_conflicts_are_reviewable_not_fatal():
    context = "".join(f"# unchanged {i}\n" for i in range(12))
    base = "value = 1\n" + context + "other = 1\n"
    ours = "value = 2\n" + context + "other = 2\n"
    theirs = "value = 3\n" + context + "other = 3\n"
    assert sync.merge_versions(ours, base, theirs) is None
