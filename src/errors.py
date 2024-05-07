# Copyright 2024 Canonical Ltd.
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


class RunnerAproxyError(RunnerError):
    """Error for setting up aproxy."""


class MissingRunnerBinaryError(Exception):
    """Error for missing runner binary."""


class ConfigurationError(Exception):
    """Error for juju configuration."""


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


class MetricsStorageError(Exception):
    """Base class for all metrics storage errors."""


class SharedFilesystemError(MetricsStorageError):
    """Base class for all shared filesystem errors."""


class CreateMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be created."""


class DeleteMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be deleted."""


class GetMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be retrieved."""


class QuarantineMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be quarantined."""


class SharedFilesystemMountError(SharedFilesystemError):
    """Represents an error related to the mounting of the shared filesystem."""


class RunnerMetricsError(Exception):
    """Base class for all runner metrics errors."""


class CorruptMetricDataError(RunnerMetricsError):
    """Represents an error with the data being corrupt."""


class GithubMetricsError(Exception):
    """Base class for all github metrics errors."""


class GithubClientError(Exception):
    """Base class for all github client errors."""


class GithubApiError(GithubClientError):
    """Represents an error when the GitHub API returns an error."""


class TokenError(GithubClientError):
    """Represents an error when the token is invalid or has not enough permissions."""


class JobNotFoundError(GithubClientError):
    """Represents an error when the job could not be found on GitHub."""


class RunnerLogsError(Exception):
    """Base class for all runner logs errors."""


class OpenStackError(Exception):
    """Base class for OpenStack errors."""


class OpenStackInvalidConfigError(OpenStackError):
    """Represents an invalid OpenStack configuration."""


class OpenStackUnauthorizedError(OpenStackError):
    """Represents an unauthorized connection to OpenStack."""


class OpenstackInstanceLaunchError(Exception):
    """Exception representing an error during instance launch process."""
