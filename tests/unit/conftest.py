import pytest
from runner import Runner


@pytest.fixture
def runner(tmp_path_factory):
    runner = Runner()
    opt_path = tmp_path_factory.mktemp("runner")
    runner.runner_path = opt_path
    runner.env_file = opt_path / ".env"
    return runner
