from unittest import mock

import pytest
from runner import Runner


@pytest.fixture
def runner(tmp_path_factory):
    runner = Runner(path="mock-org", token="mock-token")
    opt_path = tmp_path_factory.mktemp("runner")
    runner.runner_path = opt_path
    runner.env_file = opt_path / ".env"
    return runner


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    monkeypatch.setattr("charm.CronTab", mock.MagicMock())
    monkeypatch.setattr("runner.GhApi", mock.MagicMock())
    monkeypatch.setattr("runner.pylxd", mock.MagicMock())
    monkeypatch.setattr("runner.requests", mock.MagicMock())
    monkeypatch.setattr("runner.Runner._check_output", mock.MagicMock())
    monkeypatch.setattr("runner.Runner._get_runner_binary", mock.MagicMock())

    def active_count(runner_class, values=[0, 1, 2, 3]):
        return values.pop(0)

    monkeypatch.setattr("runner.Runner.active_count", active_count)
    monkeypatch.setattr("runner.time", mock.MagicMock())
