#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errors import QuarantineMetricsStorageError
from metrics_common import storage
from metrics_common.storage import MetricsStorage


@pytest.fixture(autouse=True, name="filesystem_paths")
def filesystem_paths_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Mock the hardcoded filesystem paths."""
    fs_quarantine_path = tmp_path / "quarantine"
    fs_quarantine_path.mkdir()
    runner_storage_path = tmp_path / "runner-fs"
    monkeypatch.setattr(storage, "FILESYSTEM_QUARANTINE_PATH", fs_quarantine_path)
    return {"quarantine": fs_quarantine_path, "runner": runner_storage_path}


def test_quarantine(filesystem_paths: dict[str, Path], tmp_path: Path):
    """
    arrange: Create a storage for a runner with a file in it.
    act: Call quarantine.
    assert: The shared filesystem is moved to the quarantine.
    """
    runner_name = secrets.token_hex(16)
    storage_manager = MagicMock()

    filesystem_paths["quarantine"].mkdir()
    filesystem_paths["runner"].mkdir()
    filesystem_paths["runner"].joinpath(runner_name).mkdir()
    with (filesystem_paths["runner"] / runner_name / "test.txt").open("w", encoding="utf-8") as f:
        f.write("foo bar")

    storage_manager.get.return_value = MetricsStorage(runner_name=runner_name, path=filesystem_paths["runner"].joinpath(runner_name))

    storage.move_to_quarantine(storage_manager, runner_name)

    tarfile_path = filesystem_paths["quarantine"].joinpath(runner_name).with_suffix(".tar.gz")
    assert tarfile_path.exists()
    tarfile.open(tarfile_path).extractall(path=tmp_path)
    assert tmp_path.joinpath(f"{runner_name}/test.txt").exists()
    assert tmp_path.joinpath(f"{runner_name}/test.txt").read_text(encoding="utf-8") == "foo bar"
    storage_manager.delete.assert_called_once()


def test_quarantine_raises_error(filesystem_paths: dict[str, Path]):
    """
    arrange: No specific storage is created for the runner
    act: Call quarantine.
    assert: A QuarantineMetricsStorageError is raised.
    """
    runner_name = secrets.token_hex(16)
    storage_manager = MagicMock()
    storage_manager.get.return_value = MetricsStorage(runner_name=runner_name, path=filesystem_paths["runner"].joinpath(runner_name))


    with pytest.raises(QuarantineMetricsStorageError):
        storage.move_to_quarantine(storage_manager, runner_name)
