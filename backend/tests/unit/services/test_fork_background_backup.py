"""Scheduled backups must not query locked or unknown printers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services import github_backup


@pytest.mark.asyncio
@pytest.mark.parametrize("developer_mode", [None, False, True])
async def test_backup_calibration_queries_require_confirmed_developer_mode(developer_mode):
    printer = SimpleNamespace(id=7, serial_number="test-printer")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [printer]
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    client = SimpleNamespace(
        state=SimpleNamespace(connected=True, developer_mode=developer_mode),
        get_kprofiles=AsyncMock(return_value=[]),
    )
    files = {}
    with patch.object(github_backup.printer_manager, "get_client", return_value=client):
        await github_backup.GitHubBackupService()._collect_kprofiles(db, files)
    assert client.get_kprofiles.await_count == (4 if developer_mode is True else 0)
    assert files == {}
