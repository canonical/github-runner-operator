# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest.mock

import pytest

from tests.unit.mock import MockGhapiClient, MockPylxdClient


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path):
    monkeypatch.setattr("lxd.pylxd.Client", MockPylxdClient)
    monkeypatch.setattr("runner.time", unittest.mock.MagicMock())
    monkeypatch.setattr("runner.execute_command", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.GhApi", MockGhapiClient)
    monkeypatch.setattr("runner_manager.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.pylxd.Client", MockPylxdClient)
    monkeypatch.setattr("utilities.time", unittest.mock.MagicMock())
