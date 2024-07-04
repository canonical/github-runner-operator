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
import invoke.runners
import openstack.compute.v2.server
from pydantic.networks import IPvAnyAddress

from charm_state import (
    COS_AGENT_INTEGRATION_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    DENYLIST_CONFIG_NAME,
    DOCKERHUB_MIRROR_CONFIG_NAME,
    GROUP_CONFIG_NAME,
    LABELS_CONFIG_NAME,
    MONGO_DB_INTEGRATION_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    OPENSTACK_IMAGE_BUILD_UNIT_CONFIG_NAME,
    OPENSTACK_NETWORK_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    RUNNER_STORAGE_CONFIG_NAME,
    TEST_MODE_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    VM_CPU_CONFIG_NAME,
    VM_DISK_CONFIG_NAME,
    VM_MEMORY_CONFIG_NAME,
    SSHDebugConnection,
)

T = TypeVar("T")

# DC060: Docstrings have been abbreviated for factories, checking for docstrings on model
# attributes can be skipped.


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
    """Mock github-runner charm unit."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    # The name attribute is special for MagicMock. Must be set after object creation.


class MockGithubRunnerCharmAppFactory(factory.Factory):
    """Mock github-runner charm app."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    planned_units: int = 1
    # The name attribute is special for MagicMock. Must be set after object creation.


class MockGithubRunnerCharmModelFactory(factory.Factory):
    """Mock github-runner charm model."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    relations: dict[str, list] = factory.Dict(
        {
            COS_AGENT_INTEGRATION_NAME: [],
            DEBUG_SSH_INTEGRATION_NAME: [],
            MONGO_DB_INTEGRATION_NAME: [],
        }
    )


class MockGithubRunnerCharmFactory(factory.Factory):
    """Mock GithubRunnerCharm."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    unit = factory.SubFactory(MockGithubRunnerCharmUnitFactory)
    app = factory.SubFactory(MockGithubRunnerCharmAppFactory)
    model = factory.SubFactory(MockGithubRunnerCharmModelFactory)
    config = factory.Dict(
        {
            DENYLIST_CONFIG_NAME: "",
            DOCKERHUB_MIRROR_CONFIG_NAME: "",
            GROUP_CONFIG_NAME: "default",
            LABELS_CONFIG_NAME: "",
            OPENSTACK_CLOUDS_YAML_CONFIG_NAME: "",
            OPENSTACK_NETWORK_CONFIG_NAME: "external",
            OPENSTACK_FLAVOR_CONFIG_NAME: "m1.small",
            OPENSTACK_IMAGE_BUILD_UNIT_CONFIG_NAME: -1,
            PATH_CONFIG_NAME: factory.Sequence(lambda n: f"mock_path_{n}"),
            RECONCILE_INTERVAL_CONFIG_NAME: 10,
            RUNNER_STORAGE_CONFIG_NAME: "juju-storage",
            TEST_MODE_CONFIG_NAME: "",
            TOKEN_CONFIG_NAME: factory.Sequence(lambda n: f"mock_token_{n}"),
            USE_APROXY_CONFIG_NAME: False,
            VIRTUAL_MACHINES_CONFIG_NAME: 1,
            VM_CPU_CONFIG_NAME: 2,
            VM_MEMORY_CONFIG_NAME: "7GiB",
            VM_DISK_CONFIG_NAME: "10GiB",
        }
    )


def get_mock_github_runner_charm() -> MagicMock:
    """Create a MagicMock of github-runner charm.

    Returns:
        The MagicMock object with github-runner charm attributes.
    """
    mock_charm = MockGithubRunnerCharmFactory()
    # The name attribute is special for MagicMock. Must be set after object creation.
    mock_charm.unit.name = "github-runner/0"
    mock_charm.app.name = "github-runner"
    return mock_charm


class MockOpenstackServer(factory.Factory):
    """Mock Openstack server instance."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = openstack.compute.v2.server.Server

    status = "ACTIVE"


class MockSSHRunResult(factory.Factory):
    """Mock SSH run result."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = invoke.runners.Result

    exited = 0
    stdout = ""
    stderr = ""
