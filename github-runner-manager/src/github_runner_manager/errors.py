# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""
from __future__ import annotations


class RunnerError(Exception):
    """Generic runner error as base exception."""


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class MissingServerConfigError(RunnerError):
    """Error for unable to create runner due to missing server configurations."""


class IssueMetricEventError(Exception):
    """Represents an error when issuing a metric event."""


class RunnerMetricsError(Exception):
    """Base class for all runner metrics errors."""


class GithubMetricsError(Exception):
    """Base class for all github metrics errors."""


class PlatformClientError(Exception):
    """Base class for all github client errors."""


class PlatformApiError(PlatformClientError):
    """Represents an error when the GitHub API returns an error."""


class TokenError(PlatformClientError):
    """Represents an error when the token is invalid or has not enough permissions."""


class JobNotFoundError(PlatformClientError):
    """Represents an error when the job could not be found on the platform."""


class CloudError(Exception):
    """Base class for cloud (as e.g. OpenStack) errors."""


class OpenStackError(CloudError):
    """Base class for OpenStack errors."""


class OpenStackInvalidConfigError(OpenStackError):
    """Represents an invalid OpenStack configuration."""


class SSHError(Exception):
    """Represents an error while interacting with SSH."""


class KeyfileError(SSHError):
    """Represents missing keyfile for SSH."""


class ReconcileError(Exception):
    """Base class for all reconcile errors."""


class OpenstackHealthCheckError(Exception):
    """Base class for all health check errors."""


class LockError(Exception):
    """Base class for lock errors."""
