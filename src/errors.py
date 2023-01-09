# TODO Review the errors and handling.
class RunnerError(Exception):
    """Generic runner error."""


class RunnerExecutionError(RunnerError):
    """Error for executing commands on runner."""


class RunnerFileLoadError(RunnerError):
    """Error for executing commands on runner."""


class RunnerCreateError(RunnerError):
    """Error for runner creation failure."""


class RunnerRemoveError(RunnerError):
    """Error for runner removal failure."""


class RunnerStartError(RunnerError):
    """Error for runner start failure."""


class RunnerBinaryError(Exception):
    """Error of getting runner binary."""
