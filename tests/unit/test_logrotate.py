#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from pathlib import Path
from random import randint
from unittest.mock import MagicMock

import charms.operator_libs_linux.v1.systemd
import pytest

import logrotate
from errors import LogrotateSetupError


@pytest.fixture(name="systemd_mock")
def systemd_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the systemd module."""
    mock = MagicMock(spec=charms.operator_libs_linux.v1.systemd)
    mock.service_running.return_value = True
    mock.SystemdError = charms.operator_libs_linux.v1.systemd.SystemdError
    monkeypatch.setattr(logrotate, "systemd", mock)
    return mock


@pytest.fixture(name="logrotate_dir")
def logrotate_dir_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary directory for logrotate config files."""
    logrotate_dir = tmp_path / "logrotate.d"
    logrotate_dir.mkdir()
    monkeypatch.setattr(logrotate, "LOGROTATE_CONFIG_DIR", logrotate_dir)
    return logrotate_dir


@pytest.mark.usefixtures("logrotate_dir")
def test_setup_enables_logrotate_timer(systemd_mock: MagicMock):
    """
    arrange: Mock service_running command to return False.
    act: Setup logrotate.
    assert: The commands to enable and start the logrotate timer are called.
    """
    systemd_mock.service_running.return_value = False

    logrotate.setup()

    systemd_mock.service_enable.assert_called_once_with(logrotate.LOG_ROTATE_TIMER_SYSTEMD_SERVICE)
    systemd_mock.service_start.assert_called_once_with(logrotate.LOG_ROTATE_TIMER_SYSTEMD_SERVICE)


@pytest.mark.usefixtures("logrotate_dir")
def test_setup_raises_error(systemd_mock: MagicMock):
    """
    arrange: Mock service_enable command to raise a SystemdError.
    act: Setup logrotate.
    assert: The expected error is raised.
    """
    systemd_mock.service_enable.side_effect = charms.operator_libs_linux.v1.systemd.SystemdError(
        "error"
    )

    with pytest.raises(LogrotateSetupError) as exc_info:
        logrotate.setup()
    assert "Not able to setup logrotate" in str(exc_info.value)


@pytest.mark.usefixtures("systemd_mock")
def test_setup_writes_logrotate_config(logrotate_dir: Path):
    """
    arrange: Change paths for the logrotate config directory.
    act: Setup logrotate.
    assert: The expected logrotate configs are written.
    """
    logrotate.setup()
    assert logrotate.LOGROTATE_CONFIG_DIR.is_dir()
    assert (logrotate_dir / logrotate.METRICS_LOGROTATE_CONFIG.name).exists()
    assert (logrotate_dir / logrotate.REACTIVE_LOGROTATE_CONFIG.name).exists()


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("notifempty", [True, False])
@pytest.mark.parametrize("frequency", [freq for freq in logrotate.LogrotateFrequency])
@pytest.mark.usefixtures("logrotate_dir")
def test__write_config(
    create: bool,
    notifempty: bool,
    frequency: logrotate.LogrotateFrequency,
    logrotate_dir: Path,
    tmp_path: Path,
):
    """
    arrange: Change paths for the logrotate config and the log file.
        Arrange multiple LogrotateConfig instances using all parameter combinations.
    act: Setup logrotate.
    assert: The expected logrotate config is created.
    """
    name = secrets.token_hex(16)
    log_path_glob_pattern = str(tmp_path / "metrics.log.*")
    rotate = randint(0, 11)

    logrotate_config = logrotate.LogrotateConfig(
        name=name,
        log_path_glob_pattern=log_path_glob_pattern,
        rotate=rotate,
        create=create,
        notifempty=notifempty,
        frequency=frequency,
    )

    logrotate._write_config(logrotate_config)

    expected_logrotate_config = f"""{log_path_glob_pattern} {{
{frequency}
rotate {rotate}
missingok
{"notifempty" if notifempty else "ifempty"}
{"create" if create else "nocreate"}
}}
"""
    assert (
        logrotate_dir / name
    ).read_text() == expected_logrotate_config, "Logrotate config is not as expected."
