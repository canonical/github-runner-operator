from unittest.mock import MagicMock

import factory

from charm_state import COS_AGENT_INTEGRATION_NAME, DEBUG_SSH_INTEGRATION_NAME


class MockGithubRunnerCharmUnitFactory(factory.Factory):
    class Meta:
        model = MagicMock

    name = "github-runner/0"


class MockGithubRunnerCharmAppFactory(factory.Factory):
    """Mock github-runner charm app."""

    class Meta:
        model = MagicMock

    planned_units = 1
    name = "github-runner"


class MockGithubRunnerCharmModelFactory(factory.Factory):
    """Mock github-runner charm model."""

    class Meta:
        model = MagicMock

    relations = {COS_AGENT_INTEGRATION_NAME: [], DEBUG_SSH_INTEGRATION_NAME: []}


class MockGithubRunnerCharmFactory(factory.Factory):
    """Mock GithubRunnerCharm."""

    class Meta:
        model = MagicMock

    unit = factory.SubFactory(MockGithubRunnerCharmUnitFactory)
    app = factory.SubFactory(MockGithubRunnerCharmAppFactory)
    model = factory.SubFactory(MockGithubRunnerCharmModelFactory)

    @factory.sequence
    def config(n):
        return {
            "path": f"mock_path_{n}",
            "token": f"mock_token_{n}",
            "group": "default",
            "virtual-machines": 1,
            "vm-cpu": 2,
            "vm-memory": "7GiB",
            "vm-disk": "10GiB",
            "reconcile-interval": 10,
            "test-mode": "",
            "denylist": "",
            "dockerhub-mirror": "",
            "runner-storage": "juju-storage",
            "experimental-use-aproxy": False,
        }
