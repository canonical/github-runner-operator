# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import os
from pathlib import Path

import pytest

from github_runner_manager.cli import _ensure_log_path, _resolve_log_path


def test_resolve_log_path_with_xdg_default(tmp_path, monkeypatch):
    """Arrange: Set XDG_STATE_HOME to tmp path.

    Act: Resolve log path with None.

    Assert: Path points to XDG github-runner/logs/manager.log under tmp.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path = _resolve_log_path(None)
    assert path == tmp_path / "github-runner" / "logs" / "manager.log"


def test_resolve_log_path_with_custom_dir(tmp_path):
    """Arrange: Choose a custom directory.

    Act: Resolve log path with that directory.

    Assert: Path is <custom>/manager.log.
    """
    path = _resolve_log_path(str(tmp_path))
    assert path == tmp_path / "manager.log"


def test_ensure_log_path_creates_dir_and_is_writable(tmp_path):
    """Arrange: Define a nested target directory.

    Act: Ensure log path, creating parents as needed.

    Assert: File parent exists and is writable; filename is manager.log.
    """
    target_dir = tmp_path / "nested" / "logs"
    log_file = _ensure_log_path(str(target_dir))
    assert log_file == target_dir / "manager.log"
    assert log_file.parent.is_dir()
    assert os.access(log_file.parent, os.W_OK)
