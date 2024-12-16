# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""
from __future__ import annotations


class RunnerError(Exception):
    """Generic runner error as base exception."""


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class RunnerStartError(RunnerError):
    """Error for runner start failure."""


class MissingServerConfigError(RunnerError):
    """Error for unable to create runner due to missing server configurations."""


class IssueMetricEventError(Exception):
    """Represents an error when issuing a metric event."""


class MetricsStorageError(Exception):
    """Base class for all metrics storage errors."""


class CreateMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be created."""


class DeleteMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be deleted."""


class GetMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be retrieved."""


class QuarantineMetricsStorageError(MetricsStorageError):
    """Represents an error when the metrics storage could not be quarantined."""


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
