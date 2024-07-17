#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Logrotate setup and configuration."""
from enum import Enum
from pathlib import Path

from charms.operator_libs_linux.v1 import systemd
from pydantic import BaseModel

from errors import LogrotateSetupError
from metrics.events import METRICS_LOG_PATH
from metrics.runner_logs import RUNNER_LOGS_DIR_PATH
from reactive.runner_manager import REACTIVE_RUNNER_LOG_DIR

LOG_ROTATE_TIMER_SYSTEMD_SERVICE = "logrotate.timer"


LOGROTATE_CONFIG_DIR = Path("/etc/logrotate.d")


class LogrotateFrequency(str, Enum):
    """The frequency of log rotation.

    Attributes:
        DAILY: Rotate the log daily.
        WEEKLY: Rotate the log weekly.
        MONTHLY: Rotate the log monthly.
        YEARLY: Rotate the log yearly.
    """

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class LogrotateConfig(BaseModel):
    """Configuration for logrotate.

    Attributes:
        name: The name of the logrotate configuration.
        log_path_glob_pattern: The glob pattern for the log path.
        rotate: The number of log files to keep.
        create: Whether to create the log file if it does not exist.
        notifempty: Whether to not rotate the log file if it is empty.
        frequency: The frequency of log rotation.
    """

    name: str
    log_path_glob_pattern: str
    rotate: int
    create: bool
    notifempty: bool = True
    frequency: LogrotateFrequency = LogrotateFrequency.WEEKLY


# Set rotate param to 0 to not keep the old metrics log file to avoid sending the
# metrics to Loki twice, which may happen if there is a corrupt log scrape configuration.
METRICS_LOGROTATE_CONFIG = LogrotateConfig(
    name="github-runner-metrics",
    log_path_glob_pattern=str(METRICS_LOG_PATH),
    rotate=0,
    create=True,
)

RUNNER_LOGROTATE_CONFIG = LogrotateConfig(
    name="github-runner-logs",
    log_path_glob_pattern=f"{RUNNER_LOGS_DIR_PATH}/.*",
    rotate=0,
    create=False,
)

REACTIVE_LOGROTATE_CONFIG = LogrotateConfig(
    name="reactive-runner",
    log_path_glob_pattern=f"{REACTIVE_RUNNER_LOG_DIR}/.*",
    rotate=0,
    create=False,
    notifempty=False,
    frequency=LogrotateFrequency.DAILY,
)


def setup() -> None:
    """Enable and configure logrotate.

    Raises:
        LogrotateSetupError: If the logrotate.timer cannot be enabled.
    """
    try:
        _enable()
    except _EnableLogRotateError as error:
        raise LogrotateSetupError("Not able to setup logrotate") from error

    _configure()


class _EnableLogRotateError(Exception):
    """Raised when the logrotate.timer cannot be enabled and started."""


def _enable() -> None:
    """Enable and start the logrotate timer if it is not running.

    Raises:
        _EnableLogRotateError: If the logrotate.timer cannot be enabled and started.
    """
    try:
        systemd.service_enable(LOG_ROTATE_TIMER_SYSTEMD_SERVICE)
        if not systemd.service_running(LOG_ROTATE_TIMER_SYSTEMD_SERVICE):
            systemd.service_start(LOG_ROTATE_TIMER_SYSTEMD_SERVICE)
    except systemd.SystemdError as exc:
        raise _EnableLogRotateError from exc


def _configure() -> None:
    """Configure logrotate."""
    _write_config(REACTIVE_LOGROTATE_CONFIG)
    _write_config(METRICS_LOGROTATE_CONFIG)
    _write_config(RUNNER_LOGROTATE_CONFIG)


def _write_config(logrotate_config: LogrotateConfig) -> None:
    """Write a particular logrotate config to disk.

    Args:
        logrotate_config: The logrotate config.
    """
    logrotate_config_file = LOGROTATE_CONFIG_DIR / logrotate_config.name
    logrotate_config_file.write_text(
        f"""{logrotate_config.log_path_glob_pattern} {{
{logrotate_config.frequency}
rotate {logrotate_config.rotate}
missingok
{"notifempty" if logrotate_config.notifempty else ""}
{"create" if logrotate_config.create else ""}
}}
""",
        encoding="utf-8",
    )
