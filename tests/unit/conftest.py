from functools import partial
from unittest import mock

import pytest
from runner import RunnerManager


def _rm_factory_wrapper(tmp_path, rm_factory, *args, **kwargs):
    runner_manager = rm_factory(*args, **kwargs)
    runner_manager.runner_bin_path = tmp_path / "runner.tgz"
    runner_manager.env_file = tmp_path / "env"
    return runner_manager


@pytest.fixture
def runner_manager(tmp_path):
    return _rm_factory_wrapper(
        tmp_path, RunnerManager, "org", "token", "app", "container"
    )


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path):
    monkeypatch.setattr("runner.GhApi", mock.MagicMock())
    monkeypatch.setattr("runner.pylxd", mock.MagicMock())
    monkeypatch.setattr("runner.requests", mock.MagicMock())
    monkeypatch.setattr("runner.RunnerManager._check_output", mock.MagicMock())
    monkeypatch.setattr("runner.time", mock.MagicMock())
    monkeypatch.setattr(
        "charm.RunnerManager", partial(_rm_factory_wrapper, tmp_path, RunnerManager)
    )
