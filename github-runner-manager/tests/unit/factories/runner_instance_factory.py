# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for Runner instance objects."""

import secrets
from datetime import datetime, timezone

import factory

from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.manager.runner_manager import RunnerInstance
from github_runner_manager.manager.vm_manager import VM, VMState
from github_runner_manager.openstack_cloud.openstack_cloud import OpenstackInstance
from github_runner_manager.platform.platform_provider import (
    PlatformRunnerHealth,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import SelfHostedRunner


class InstanceIDFactory(factory.Factory):
    """Factory class for creating InstanceID."""

    class Meta:
        """Meta class for InstanceID.

        Attributes:
            model: The metadata reference model.
        """

        model = InstanceID

    prefix = factory.Faker("word")
    reactive = factory.Iterator([True, False, None])
    suffix = factory.LazyAttribute(lambda _: secrets.token_hex(6))


class RunnerMetadataFactory(factory.Factory):
    """Factory for creating RunnerMetadata instances."""

    class Meta:
        """Meta class for RunnerMetadata.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerMetadata

    platform_name = factory.Faker("word", ext_word_list=["github"])
    runner_id = str(factory.Faker("random_int", min=1, max=10000))
    url = factory.Faker("url")


class CloudRunnerInstanceFactory(factory.Factory):
    """Factory for creating CloudRunnerInstance instances."""

    class Meta:
        """Meta class for CloudRunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = VM

    instance_id = factory.SubFactory(InstanceIDFactory)
    metadata = factory.SubFactory(RunnerMetadataFactory)
    state = VMState.ACTIVE
    created_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))

    @classmethod
    def from_self_hosted_runner(cls, self_hosted_runner: SelfHostedRunner) -> VM:
        """Construct CloudRunnerInstance associated to self hosted runner.

        Args:
            self_hosted_runner: The target self hosted runner to associate.

        Returns:
            The Instantiated CloudRunnerInstance.
        """
        return CloudRunnerInstanceFactory(
            instance_id=self_hosted_runner.identity.instance_id,
            metadata=RunnerMetadataFactory(runner_id=str(self_hosted_runner.id)),
        )


class OpenstackInstanceFactory(factory.Factory):
    """Factory for creating OpenstackInstance instances."""

    class Meta:
        """Meta class for RunnerIdentity.

        Attributes:
            model: The metadata reference model.
        """

        model = OpenstackInstance

    addresses = factory.List(factory.Faker("ipv4") for _ in range(3))
    created_at = factory.LazyFunction(datetime.now)
    instance_id = InstanceIDFactory()
    server_id = factory.Faker("uuid4")
    status = factory.Faker("word")
    metadata = RunnerMetadataFactory()


class RunnerIdentityFactory(factory.Factory):
    """Factory for creating RunnerIdentity instances."""

    class Meta:
        """Meta class for RunnerIdentity.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerIdentity

    instance_id = factory.SubFactory(InstanceIDFactory)
    metadata = factory.SubFactory(RunnerMetadataFactory)


class PlatformRunnerHealthFactory(factory.Factory):
    """Factory for creating PlatformRunnerHealth instances."""

    class Meta:
        """Meta class for PlatformRunnerHealth.

        Attributes:
            model: The metadata reference model.
        """

        model = PlatformRunnerHealth

    identity = factory.SubFactory(RunnerIdentityFactory)
    online = factory.Faker("boolean")
    busy = factory.Faker("boolean")
    deletable = factory.Faker("boolean")
    runner_in_platform = factory.Faker("boolean")


class RunnerInstanceFactory(factory.Factory):
    """Factory for creating RunnerInstance instances."""

    class Meta:
        """Meta class for RunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerInstance

    name = factory.Faker("name")
    instance_id = factory.SubFactory(InstanceIDFactory)
    metadata = factory.LazyAttribute(lambda _: {"key": "value"})
    platform_state = factory.LazyFunction(lambda: secrets.choice(list(PlatformRunnerState)))
    platform_health = factory.LazyAttribute(
        lambda obj: PlatformRunnerHealthFactory(
            identity=RunnerIdentityFactory(instance_id=obj.instance_id)
        )
    )
    cloud_state = VMState.ACTIVE

    @classmethod
    def from_state(
        cls, cloud_runner: VM, platform_health: PlatformRunnerHealth | None = None
    ) -> RunnerInstance:
        """Generate RunnerInstance from cloud runner and platform runner states.

        Args:
            cloud_runner: The cloud runner to generate state from.
            platform_health: The platform runner to generate state from.

        Returns:
            The generated RunnerInstance.
        """
        return RunnerInstance(
            name=cloud_runner.instance_id.name,
            instance_id=cloud_runner.instance_id,
            metadata=cloud_runner.metadata,
            platform_state=(
                PlatformRunnerState.from_platform_health(platform_health)
                if platform_health is not None
                else None
            ),
            platform_health=platform_health,
            cloud_state=cloud_runner.state,
        )


class SelfHostedRunnerFactory(factory.Factory):
    """Factory for creating SelfHostedRunner instances."""

    class Meta:
        """Meta class for SelfHostedRunner.

        Attributes:
            model: The metadata reference model.
        """

        model = SelfHostedRunner

    busy = factory.Faker("boolean")
    id = factory.Faker("random_int", min=1, max=10000)
    labels = factory.List([factory.Faker("word") for _ in range(3)])
    status = factory.Faker("word", ext_word_list=["online", "offline"])
    deletable = factory.Faker("boolean")
    # identity.metadata.runner_id should be equal to the id attribute.
    identity = factory.LazyAttribute(
        lambda obj: RunnerIdentityFactory(
            metadata=RunnerMetadata(platform_name="github", runner_id=obj.id),
        )
    )
