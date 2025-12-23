# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for utilities module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from github_runner_manager.utilities import get_base_dir, get_state_dir, get_reactive_log_dir


def test_get_base_dir_explicit_parameter(tmp_path: Path):
    """
    arrange: Given an explicit base directory path.
    act: Call get_base_dir with the explicit path.
    assert: The returned path matches the explicit path and directory is created.
    """
    base_dir = tmp_path / "custom_base"
    
    result = get_base_dir(str(base_dir))
    
    assert result == base_dir.resolve()
    assert result.exists()
    assert result.is_dir()


def test_get_base_dir_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given GITHUB_RUNNER_MANAGER_BASE_DIR environment variable is set.
    act: Call get_base_dir without explicit parameter.
    assert: The returned path matches the environment variable and directory is created.
    """
    base_dir = tmp_path / "env_base"
    monkeypatch.setenv("GITHUB_RUNNER_MANAGER_BASE_DIR", str(base_dir))
    
    result = get_base_dir()
    
    assert result == base_dir.resolve()
    assert result.exists()
    assert result.is_dir()


def test_get_base_dir_xdg_state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given XDG_STATE_HOME is set.
    act: Call get_base_dir.
    assert: Returns XDG_STATE_HOME/github-runner-manager.
    """
    state_home = tmp_path / "state_home"
    state_home.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_BASE_DIR", raising=False)
    
    result = get_base_dir()
    
    assert result == state_home / "github-runner-manager"
    assert result.exists()
    assert result.is_dir()


def test_get_base_dir_default_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given no environment variables set.
    act: Call get_base_dir.
    assert: Returns ~/.local/state/github-runner-manager.
    """
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("GITHUB_RUNNER_MANAGER_BASE_DIR", raising=False)
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_base_dir()
    
    expected = tmp_path / ".local" / "state" / "github-runner-manager"
    assert result == expected
    assert result.exists()
    assert result.is_dir()


def test_get_state_dir_creates_subdirectory(tmp_path: Path):
    """
    arrange: Given a base directory.
    act: Call get_state_dir with explicit base directory.
    assert: Returns base_dir/state and directory is created.
    """
    base_dir = tmp_path / "base"
    
    result = get_state_dir(str(base_dir))
    
    expected = base_dir / "state"
    assert result == expected
    assert result.exists()
    assert result.is_dir()


def test_get_reactive_log_dir_creates_subdirectory(tmp_path: Path):
    """
    arrange: Given a base directory.
    act: Call get_reactive_log_dir with explicit base directory.
    assert: Returns base_dir/logs/reactive and directory is created.
    """
    base_dir = tmp_path / "base"
    
    result = get_reactive_log_dir(str(base_dir))
    
    expected = base_dir / "logs" / "reactive"
    assert result == expected
    assert result.exists()
    assert result.is_dir()


def test_get_base_dir_expands_user_path(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Given a base directory path with tilde.
    act: Call get_base_dir with tilde path.
    assert: The path is expanded and resolved.
    """
    result = get_base_dir("~/test_base")
    
    assert "~" not in str(result)
    assert result.is_absolute()


def test_subdirectories_hierarchy(tmp_path: Path):
    """
    arrange: Given a base directory.
    act: Call all directory functions.
    assert: Proper subdirectory hierarchy is created.
    """
    base_dir = tmp_path / "base"
    
    state_dir = get_state_dir(str(base_dir))
    reactive_log_dir = get_reactive_log_dir(str(base_dir))
    
    assert state_dir.parent == base_dir
    assert reactive_log_dir.parent.parent == base_dir
    assert reactive_log_dir.parent.name == "logs"
    assert state_dir.name == "state"
    assert reactive_log_dir.name == "reactive"
