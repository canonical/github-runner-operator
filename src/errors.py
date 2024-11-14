# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""
from __future__ import annotations

from typing import Union

# we import the errors from the module, these are used in the charm
from github_runner_manager.errors import (  # noqa: F401  pylint: disable=unused-import
    CreateMetricsStorageError,
    DeleteMetricsStorageError,
    GetMetricsStorageError,
    GithubClientError,
    GithubMetricsError,
    MetricsStorageError,
    RunnerError,
    TokenError,
)


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class RunnerFileLoadError(RunnerError):
    """Error for loading file on runner."""


class RunnerRemoveError(RunnerError):
    """Error for runner removal failure."""


class RunnerBinaryError(RunnerError):
    """Error of getting runner binary."""


class RunnerAproxyError(RunnerError):
    """Error for setting up aproxy."""


class MissingServerConfigError(RunnerError):
    """Error for unable to create runner due to missing server configurations."""


class MissingRunnerBinaryError(Exception):
    """Error for missing runner binary."""


class ConfigurationError(Exception):
    """Error for juju configuration."""


class MissingMongoDBError(Exception):
    """Error for missing integration data."""


class LxdError(Exception):
    """Error for executing LXD actions."""


class SubprocessError(Exception):
    """Error for Subprocess calls.

    Attributes:
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


class IssueMetricEventError(Exception):
    """Represents an error when issuing a metric event."""


class LogrotateSetupError(Exception):
    """Represents an error raised when logrotate cannot be setup."""


class SharedFilesystemError(MetricsStorageError):
    """Base class for all shared filesystem errors."""


class SharedFilesystemMountError(SharedFilesystemError):
    """Represents an error related to the mounting of the shared filesystem."""


class RunnerLogsError(Exception):
    """Base class for all runner logs errors."""
