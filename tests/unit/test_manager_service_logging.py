# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
import os

import pytest

import src.manager_service as manager_service


def test_setup_service_file_writes_execstart_with_log_dir(tmp_path, monkeypatch):
    """Arrange: Point service path and log dir constants to temp locations.

    Act: Render the systemd unit via _setup_service_file.

    Assert: ExecStart contains --log-path <dir> and no stdout/stderr redirection.
    """
    service_path = tmp_path / "github-runner-manager.service"
    monkeypatch.setattr(
        manager_service,
        "GITHUB_RUNNER_MANAGER_SYSTEMD_SERVICE_PATH",
        service_path,
        raising=False,
    )

    # Point log dir constant to a temp dir so the content is predictable
    log_dir = tmp_path / "var" / "log" / "github-runner-manager"
    monkeypatch.setattr(
        manager_service,
        "GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR",
        log_dir,
        raising=False,
    )

    cfg = tmp_path / "config.yaml"
    cfg.write_text("{}", encoding="utf-8")

    dummy_log_file = tmp_path / "unit.log"

    manager_service._setup_service_file(cfg, dummy_log_file, "INFO")

    content = service_path.read_text(encoding="utf-8")
    assert f"--log-path {str(log_dir)}" in content
    assert "StandardOutput=" not in content
    assert "StandardError=" not in content


def test_ensure_log_file_creates_file(tmp_path, monkeypatch):
    """Arrange: Mock chown and point log dir to tmp.

    Act: Call _ensure_log_file with a unit name.

    Assert: Log file exists under the tmp dir and parent is writable.
    """
    # Avoid chown failures in test environments
    monkeypatch.setattr("src.manager_service.shutil.chown", lambda *a, **k: None)

    monkeypatch.setattr(
        manager_service,
        "GITHUB_RUNNER_MANAGER_SERVICE_LOG_DIR",
        tmp_path,
        raising=False,
    )

    logfile = manager_service._ensure_log_file("app/0")
    assert logfile.is_file()
    assert logfile.parent == tmp_path
    assert os.access(logfile.parent, os.W_OK)
