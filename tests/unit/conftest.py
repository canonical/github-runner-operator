# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path):
    monkeypatch.setattr("runner.GhApi", mock.MagicMock())
    monkeypatch.setattr("runner.pylxd", mock.MagicMock())
    monkeypatch.setattr("runner.requests", mock.MagicMock())
    monkeypatch.setattr("runner.time", mock.MagicMock())
    monkeypatch.setattr("runner.RunnerManager._check_output", mock.MagicMock())
    monkeypatch.setattr("runner.RunnerManager.runner_bin_path", tmp_path / "runner.tgz")
    monkeypatch.setattr("runner.RunnerManager.env_file", tmp_path / "env")
