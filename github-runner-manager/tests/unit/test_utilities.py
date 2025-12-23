# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for utilities module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from github_runner_manager.utilities import get_state_dir


def test_get_state_dir_explicit_parameter(tmp_path: Path):
    """
    arrange: Given an explicit state directory path.
    act: Call get_state_dir with the explicit path.
    assert: The returned path matches the explicit path and directory is created.
    """
    state_dir = tmp_path / "custom_state"
    
    result = get_state_dir(str(state_dir))
    
    assert result == state_dir.resolve()
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given GITHUB_RUNNER_MANAGER_STATE_DIR environment variable is set.
    act: Call get_state_dir without explicit parameter.
    assert: The returned path matches the environment variable and directory is created.
    """
    state_dir = tmp_path / "env_state"
    monkeypatch.setenv("GITHUB_RUNNER_MANAGER_STATE_DIR", str(state_dir))
    
    result = get_state_dir()
    
    assert result == state_dir.resolve()
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_xdg_runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given XDG_RUNTIME_DIR is set and writable, no explicit state dir or env var.
    act: Call get_state_dir.
    assert: Returns XDG_RUNTIME_DIR/github-runner-manager.
    """
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_STATE_DIR", raising=False)
    
    result = get_state_dir()
    
    assert result == runtime_dir / "github-runner-manager"
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_tmpdir_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given TMPDIR is set and writable, no XDG_RUNTIME_DIR.
    act: Call get_state_dir.
    assert: Returns TMPDIR/github-runner-manager.
    """
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_STATE_DIR", raising=False)
    
    result = get_state_dir()
    
    assert result == tmpdir / "github-runner-manager"
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_xdg_state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given XDG_STATE_HOME is set, no XDG_RUNTIME_DIR or TMPDIR.
    act: Call get_state_dir.
    assert: Returns XDG_STATE_HOME/github-runner-manager.
    """
    state_home = tmp_path / "state_home"
    state_home.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_STATE_DIR", raising=False)
    
    result = get_state_dir()
    
    assert result == state_home / "github-runner-manager"
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_default_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given no environment variables set.
    act: Call get_state_dir.
    assert: Returns ~/.local/state/github-runner-manager.
    """
    # Mock Path.home() to use tmp_path
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_STATE_DIR", raising=False)
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_state_dir()
    
    expected = tmp_path / ".local" / "state" / "github-runner-manager"
    assert result == expected
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_creates_directory(tmp_path: Path):
    """
    arrange: Given a state directory that doesn't exist.
    act: Call get_state_dir.
    assert: The directory is created.
    """
    state_dir = tmp_path / "new_state_dir"
    assert not state_dir.exists()
    
    result = get_state_dir(str(state_dir))
    
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_explicit_overrides_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given both explicit parameter and environment variable.
    act: Call get_state_dir with explicit parameter.
    assert: The explicit parameter takes precedence.
    """
    explicit_dir = tmp_path / "explicit"
    env_dir = tmp_path / "env"
    monkeypatch.setenv("GITHUB_RUNNER_MANAGER_STATE_DIR", str(env_dir))
    
    result = get_state_dir(str(explicit_dir))
    
    assert result == explicit_dir.resolve()
    assert result.exists()
    assert not env_dir.exists()


def test_get_state_dir_expands_user_path(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a state directory path with tilde.
    act: Call get_state_dir with tilde path.
    assert: The path is expanded and resolved.
    """
    result = get_state_dir("~/test_state")
    
    assert "~" not in str(result)
    assert result.is_absolute()


def test_get_state_dir_xdg_runtime_dir_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given XDG_RUNTIME_DIR points to non-writable directory.
    act: Call get_state_dir.
    assert: Falls back to next option (TMPDIR or XDG_STATE_HOME).
    """
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    # Make it non-writable
    runtime_dir.chmod(0o444)
    
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_STATE_DIR", raising=False)
    
    try:
        result = get_state_dir()
        # Should fall back to TMPDIR
        assert result == tmpdir / "github-runner-manager"
    finally:
        # Restore permissions for cleanup
        runtime_dir.chmod(0o755)
