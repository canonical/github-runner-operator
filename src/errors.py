# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""
from __future__ import annotations

from typing import Union

# we import the errors from the module, these are used in the charm
from github_runner_manager.errors import (  # noqa: F401  pylint: disable=unused-import
    GithubMetricsError,
    PlatformClientError,
    RunnerError,
    TokenError,
)


class ConfigurationError(Exception):
    """Error for juju configuration."""


class MissingMongoDBError(Exception):
    """Error for missing integration data."""


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


class LogrotateSetupError(Exception):
    """Represents an error raised when logrotate cannot be setup."""


class RunnerManagerApplicationError(Exception):
    """Represents an error raised with github-runner-manager application."""


class RunnerManagerApplicationInstallError(RunnerManagerApplicationError):
    """Represents an error raised when github-runner-manager application installation failed."""


class RunnerManagerApplicationStartError(RunnerManagerApplicationError):
    """Represents an error raised when github-runner-manager application start failed."""


class RunnerManagerServiceError(Exception):
    """Represents an error raised with request to github-runner-manager service."""


class RunnerManagerServiceConnectionError(RunnerManagerServiceError):
    """Represents a connection failure to the github-runner-manager service."""


class RunnerManagerServiceResponseError(RunnerManagerServiceError):
    """Represents a issue with the response to github-runner-manager service."""
