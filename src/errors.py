# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Errors used by the charm."""


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


class LxdError(Exception):
    """Error for executing LXD actions."""
