#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Logrotate setup and configuration."""

from pathlib import Path

from pydantic import BaseModel

from errors import LogrotateSetupError, SubprocessError
from utilities import execute_command

LOG_ROTATE_TIMER_SYSTEMD_SERVICE = "logrotate.timer"

SYSTEMCTL_PATH = "/usr/bin/systemctl"

LOGROTATE_CONFIG_DIR = Path("/etc/logrotate.d")


class LogrotateConfig(BaseModel):
    """Configuration for logrotate.

    Attributes:
        name: The name of the logrotate configuration.
        log_path_glob_pattern: The glob pattern for the log path.
        rotate: The number of log files to keep.
        create: Whether to create the log file if it does not exist.
    """

    name: str
    log_path_glob_pattern: str
    rotate: int
    create: bool


def setup() -> None:
    """Set up logrotate.

    Raises:
        LogrotateSetupError: If the logrotate.timer cannot be enabled.
    """
    try:
        _enable_logrotate()
    except _EnableLogRotateError as error:
        raise LogrotateSetupError("Not able to setup logrotate") from error


class _EnableLogRotateError(Exception):
    """Raised when the logrotate.timer cannot be enabled and started."""


def _enable_logrotate() -> None:
    """Enable and start the logrotate timer if it is not active.

    Raises:
        _EnableLogRotateError: If the logrotate.timer cannot be enabled and started.
    """
    try:
        execute_command(
            [SYSTEMCTL_PATH, "enable", LOG_ROTATE_TIMER_SYSTEMD_SERVICE], check_exit=True
        )

        _, retcode = execute_command(
            [SYSTEMCTL_PATH, "is-active", "--quiet", LOG_ROTATE_TIMER_SYSTEMD_SERVICE]
        )
        if retcode != 0:
            execute_command(
                [SYSTEMCTL_PATH, "start", LOG_ROTATE_TIMER_SYSTEMD_SERVICE], check_exit=True
            )
    except SubprocessError as exc:
        raise _EnableLogRotateError from exc


def configure(logrotate_config: LogrotateConfig) -> None:
    """Write a particular logrotate config to disk.

    Args:
        logrotate_config: The logrotate config.
    """
    logrotate_config_file = LOGROTATE_CONFIG_DIR / logrotate_config.name
    logrotate_config_file.write_text(
        f"""{logrotate_config.log_path_glob_pattern} {{
rotate {logrotate_config.rotate}
missingok
notifempty
{"create" if logrotate_config.create else ""}
}}
""",
        encoding="utf-8",
    )
