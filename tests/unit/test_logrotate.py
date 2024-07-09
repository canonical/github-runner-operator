#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from random import randint
from unittest.mock import MagicMock, call

import pytest

import logrotate
from errors import LogrotateSetupError, SubprocessError


@pytest.fixture(name="exec_command")
def exec_command_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock(return_value=("", 0))
    monkeypatch.setattr("logrotate.execute_command", mock)
    return mock


def test_setup_enables_logrotate_timer(exec_command: MagicMock):
    """
    arrange: Mock execute command to return error for the is-active call and \
        non-error for the remaining calls.
    act: Setup logrotate.
    assert: The commands to enable and start the logrotate timer are called.
    """

    def side_effect(*args, **kwargs):
        """Mock side effect function that returns non-zero exit code.

        Args:
            args: Placeholder for positional arguments for lxd exec command.
            kwargs: Placeholder for keyword arguments for lxd exec command.

        Returns:
            A tuple of return value and exit code.
        """
        if "is-active" in args[0]:
            return "", 1
        return "", 0

    exec_command.side_effect = side_effect

    logrotate.setup()

    assert (
        call(["/usr/bin/systemctl", "enable", "logrotate.timer"], check_exit=True)
        in exec_command.mock_calls
    )
    assert (
        call(["/usr/bin/systemctl", "start", "logrotate.timer"], check_exit=True)
        in exec_command.mock_calls
    )


def test_setup_raises_error(exec_command: MagicMock):
    """
    arrange: Mock execute command to raise a SubprocessError.
    act: Setup logrotate.
    assert: The expected error is raised.
    """
    exec_command.side_effect = SubprocessError(
        cmd=["mock"], return_code=1, stdout="mock stdout", stderr="mock stderr"
    )

    with pytest.raises(LogrotateSetupError) as exc_info:
        logrotate.setup()
    assert "Not able to setup logrotate" in str(exc_info.value)


def test_config_logrotate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: Change paths for the logrotate config and the log file.
    act: Setup logrotate.
    assert: The expected logrotate config is created.
    """
    config_dir = tmp_path / "logrotate.d"
    config_dir.mkdir()
    monkeypatch.setattr("logrotate.LOGROTATE_CONFIG_DIR", config_dir)

    name = secrets.token_hex(16)
    log_path_glob_pattern = str(tmp_path / "metrics.log.*")
    rotate = randint(0, 11)

    create_vals = [True, False]
    notifempty_vals = [True, False]

    for create in create_vals:
        for notifempty in notifempty_vals:
            for frequency in logrotate.LogrotateFrequency:
                logrotate_config = logrotate.LogrotateConfig(
                    name=name,
                    log_path_glob_pattern=log_path_glob_pattern,
                    rotate=rotate,
                    create=create,
                    notifempty=notifempty,
                    frequency=frequency,
                )

                logrotate.configure(logrotate_config)

                expected_logrotate_config = f"""{log_path_glob_pattern} {{
{frequency}
rotate {rotate}
missingok
{"notifempty" if notifempty else ""}
{"create" if create else ""}
}}
"""
                assert (
                    config_dir / name
                ).read_text() == expected_logrotate_config, "Logrotate config is not as expected."
