# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""
from __future__ import annotations

from typing import Union


class RunnerError(Exception):
    """Generic runner error as base exception."""


class RunnerExecutionError(RunnerError):
    """Error for executing commands on runner."""


class RunnerFileLoadError(RunnerError):
    """Error for loading file on runner."""


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class RunnerRemoveError(RunnerError):
    """Error for runner removal failure."""


class RunnerStartError(RunnerError):
    """Error for runner start failure."""


class RunnerBinaryError(RunnerError):
    """Error of getting runner binary."""


class MissingRunnerBinaryError(Exception):
    """Error for missing runner binary."""


class MissingConfigurationError(Exception):
    """Error for missing juju configuration.

    Attrs:
        configs: The missing configurations.
    """

    def __init__(self, configs: list[str]):
        """Construct the MissingConfigurationError.

        Args:
            configs: The missing configurations.
        """
        super().__init__(f"Missing required charm configuration: {configs}")

        self.configs = configs


class LxdError(Exception):
    """Error for executing LXD actions."""


class SubprocessError(Exception):
    """Error for Subprocess calls.

    Attrs:
        cmd: Command in list form.
        return_code: Return code of the subprocess.
        stdout: Content of stdout of the subprocess.
        stderr: Content of stderr of the subprocess.
    """

    def __init__(
        self,
        cmd: list[str],
        return_code: int,
        stdout: Union[bytes, str],
        stderr: Union[bytes, str],
    ):
        """Construct the subprocess error.

        Args:
            cmd: Command in list form.
            return_code: Return code of the subprocess.
            stdout: Content of stdout of the subprocess.
            stderr: Content of stderr of the subprocess.
        """
        super().__init__(f"[{' '.join(cmd)}] failed with return code {return_code!r}: {stderr!r}")

        self.cmd = cmd
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class LogrotateSetupError(Exception):
    """Error raised when logrotate cannot be setup."""


class SharedFilesystemError(Exception):
    """Base class for all shared filesystem errors."""

    def __init__(self, msg: str):
        """Initialize a new instance of the SharedFilesystemError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class CreateSharedFilesystemError(SharedFilesystemError):
    """Represents an error when the shared filesystem could not be created."""


class SharedFilesystemNotFoundError(SharedFilesystemError):
    """Represents an error when the shared filesystem is not found."""


class RunnerMetricsError(Exception):
    """Base class for all runner metrics errors."""

    def __init__(self, msg: str):
        """Initialize a new instance of the RunnerMetricsError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class CorruptMetricDataError(RunnerMetricsError):
    """Represents an error with the data being corrupt."""
