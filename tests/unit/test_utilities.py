# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases of utilities."""

from subprocess import CalledProcessError  # nosec B404
from unittest.mock import MagicMock

import pytest

from utilities import execute_command


def test_execute_command_with_error(monkeypatch):
    """
    arrange: Set up subprocess.run to return a result with error.
    act: Execute a command
    assert: Throw related to subprocess thrown.
    """

    def raise_called_process_error(*args, **kargs):
        raise CalledProcessError(returncode=1, cmd="mock cmd", stderr="mock stderr")

    mock_run = MagicMock()
    mock_run.return_value = mock_result = MagicMock()
    mock_result.check_returncode = raise_called_process_error
    monkeypatch.setattr("utilities.subprocess.run", mock_run)

    with pytest.raises(CalledProcessError):
        execute_command(["mock", "cmd"])
