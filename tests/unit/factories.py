# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

# The factory definitions don't need public methods
# pylint: disable=too-few-public-methods

import random
import secrets
from typing import Generic, TypeVar
from unittest.mock import MagicMock

import factory
import factory.fuzzy
from factory.faker import faker
from pydantic.networks import IPvAnyAddress

from charm import GithubRunnerCharm
from charm_state import (
    COS_AGENT_INTEGRATION_NAME,
    DEBUG_SSH_INTEGRATION_NAME,
    DENYLIST_CONFIG_NAME,
    DOCKERHUB_MIRROR_CONFIG_NAME,
    GROUP_CONFIG_NAME,
    LABELS_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
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
    Arch,
    BaseImage,
    CharmConfig,
    CharmState,
    FirewallEntry,
    GithubPath,
    GithubRepo,
    ProxyConfig,
    RunnerCharmConfig,
    RunnerStorage,
    SSHDebugConnection,
    VirtualMachineResources,
)
from runner_manager_type import GitHubRunnerStatus, RunnerInfo

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


class MockGithubRunnerCharmUnitFactory(
    factory.Factory, metaclass=BaseMetaFactory[GithubRunnerCharm]  # type: ignore
):
    """Mock github-runner charm unit."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    name = "github-runner/0"


class MockGithubRunnerCharmAppFactory(factory.Factory):
    """Mock github-runner charm app."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    planned_units = 1
    name = "github-runner"


class MockGithubRunnerCharmModelFactory(factory.Factory):
    """Mock github-runner charm model."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    relations: dict[str, list] = {COS_AGENT_INTEGRATION_NAME: [], DEBUG_SSH_INTEGRATION_NAME: []}


class MockGithubRunnerCharmFactory(
    factory.Factory, metaclass=BaseMetaFactory[GithubRunnerCharm]  # type: ignore
):
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


class ProxyConfigFactory(factory.Factory, metaclass=BaseMetaFactory[ProxyConfig]):  # type: ignore
    """Mock ProxyConfig."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = ProxyConfig

    http = "http://proxy.test:3128"
    https = "http://proxy.test:3128"
    no_proxy = "localhost, 127.0.0.1"
    use_aproxy = True


class FirewallEntryFactory(
    factory.Factory, metaclass=BaseMetaFactory[FirewallEntry]  # type: ignore
):
    """Mock FirewallEntry."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = FirewallEntry

    ip_range = faker.Faker().ipv4()


class GithubPathFactory(factory.Factory, metaclass=BaseMetaFactory[GithubPath]):  # type: ignore
    """Mock GithubPath."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = GithubRepo

    owner = faker.Faker().name()
    repo = faker.Faker().name()


class CharmConfigFactory(factory.Factory, metaclass=BaseMetaFactory[CharmConfig]):  # type: ignore
    """Mock CharmConfig."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = CharmConfig

    denylist: list[FirewallEntry] = FirewallEntryFactory.generate_batch(
        strategy=factory.CREATE_STRATEGY, size=3
    )
    dockerhub_mirror = "http://dockerhubmirror.test"
    labels = ("test", "labels")
    openstack_clouds_yaml: dict = {"clouds": {"test": {}}}
    path = GithubRepo(owner="test", repo="test")
    reconcile_interval = 5
    token = secrets.token_hex(12)


class RunnerCharmConfigFactory(
    factory.Factory, metaclass=BaseMetaFactory[RunnerCharmConfig]  # type: ignore
):
    """Mock RunnerCharmConfig."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = RunnerCharmConfig

    base_image = BaseImage.JAMMY
    virtual_machines = 2
    virtual_machine_resources = VirtualMachineResources(1, "30GiB", "50GiB")
    runner_storage = RunnerStorage.JUJU_STORAGE


class SSHDebugConnectionFactory(
    factory.Factory, metaclass=BaseMetaFactory[SSHDebugConnection]  # type: ignore
):
    """Generate PathInfos."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = SSHDebugConnection
        abstract = False

    host: IPvAnyAddress = faker.Faker().ipv4()
    port: int = factory.LazyAttribute(lambda n: random.randrange(1024, 65536))
    rsa_fingerprint: str = factory.fuzzy.FuzzyText(prefix="SHA256:")
    ed25519_fingerprint: str = factory.fuzzy.FuzzyText(prefix="SHA256:")


class CharmStateFactory(factory.Factory, metaclass=BaseMetaFactory[CharmState]):  # type: ignore
    """Mock CharmStateFactory."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = CharmState

    arch: Arch = Arch.X64
    is_metrics_logging_available: bool = faker.Faker().boolean()
    proxy_config: ProxyConfig = factory.SubFactory(ProxyConfigFactory)
    charm_config: CharmConfig = factory.SubFactory(CharmConfigFactory)
    runner_config: RunnerCharmConfig = factory.SubFactory(RunnerCharmConfigFactory)
    ssh_debug_connections: list[SSHDebugConnection] = SSHDebugConnectionFactory.create_batch(
        size=3
    )


class RunnerInfoFactory(factory.Factory, metaclass=BaseMetaFactory[RunnerInfo]):  # type: ignore
    """Mock RunnerInfoFactory."""  # noqa: DCO060

    class Meta:
        """Configuration for factory."""  # noqa: DCO060

        model = RunnerInfo

    name = faker.Faker().name()
    status = GitHubRunnerStatus.ONLINE
    busy: bool = faker.Faker().boolean()
