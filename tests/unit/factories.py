# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

# The factory definitions don't need public methods
# pylint: disable=too-few-public-methods

import random
from typing import Generic, TypeVar
from unittest.mock import MagicMock

import factory
import factory.fuzzy
from pydantic.networks import IPvAnyAddress

from charm_state import COS_AGENT_INTEGRATION_NAME, DEBUG_SSH_INTEGRATION_NAME, SSHDebugConnection

T = TypeVar("T")


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    """Used for type hints of factories."""

    # No need for docstring because it is used for type hints
    def __call__(cls, *args, **kwargs) -> T:  # noqa: N805
        """Used for type hints of factories."""  # noqa: DCO020
        return super().__call__(*args, **kwargs)  # noqa: DCO030


# The attributes of these classes are generators for the attributes of the meta class
# mypy incorrectly believes the factories don't support metaclass
class SSHDebugInfoFactory(
    factory.Factory, metaclass=BaseMetaFactory[SSHDebugConnection]  # type: ignore
):
    # Docstrings have been abbreviated for factories, checking for docstrings on model attributes
    # can be skipped.
    """Generate PathInfos."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = SSHDebugConnection
        abstract = False

    host: IPvAnyAddress = factory.Faker("ipv4")
    port: int = factory.LazyAttribute(lambda n: random.randrange(1024, 65536))
    rsa_fingerprint: str = factory.fuzzy.FuzzyText(prefix="SHA256:")
    ed25519_fingerprint: str = factory.fuzzy.FuzzyText(prefix="SHA256:")


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

    relations: dict[str, list] = {COS_AGENT_INTEGRATION_NAME: [], DEBUG_SSH_INTEGRATION_NAME: []}


class MockGithubRunnerCharmFactory(factory.Factory):
    """Mock GithubRunnerCharm."""

    class Meta:
        model = MagicMock

    unit = factory.SubFactory(MockGithubRunnerCharmUnitFactory)
    app = factory.SubFactory(MockGithubRunnerCharmAppFactory)
    model = factory.SubFactory(MockGithubRunnerCharmModelFactory)

    # Ignore N805 as the first param is not self for Factory Boy sequences.
    # See: https://factoryboy.readthedocs.io/en/stable/introduction.html#sequences
    @factory.sequence
    def config(n):  # noqa: N805
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
            "experimental-openstack-flavour": "m1.small",
            "experimental-openstack-network": "external",
            "labels": "",
        }
