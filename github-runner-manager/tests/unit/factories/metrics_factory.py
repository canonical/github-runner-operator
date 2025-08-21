# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for Metrics objects."""

import secrets
from dataclasses import dataclass
from datetime import datetime

import factory
from pydantic import NonNegativeFloat

from github_runner_manager.manager.vm_manager import CodeInformation
from github_runner_manager.metrics.events import Event, RunnerInstalled, RunnerStart, RunnerStop
from github_runner_manager.metrics.runner import (
    InstanceID,
    PostJobMetrics,
    PreJobMetrics,
    PulledMetrics,
    RunnerMetadata,
)
from tests.unit.factories.runner_instance_factory import (
    InstanceIDFactory,
    OpenstackInstanceFactory,
    RunnerMetadataFactory,
)


class EventFactory(factory.Factory):
    """Factory for creating Event instances."""

    class Meta:
        """Meta class for Event.

        Attributes:
            model: The metadata reference model.
        """

        model = Event

    timestamp = factory.Faker("unix_time", end_datetime="now")
    event = factory.LazyAttribute(lambda obj: obj.__class__.__name__.lower())


class RunnerInstalledFactory(EventFactory):
    """Factory for creating RunnerInstalled instances."""

    class Meta:
        """Meta class for RunnerInstalled.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerInstalled

    event = "runner_installed"
    flavor = factory.Faker("word", ext_word_list=["large", "xlarge"])
    duration = factory.Faker("random_int", min=1, max=3600)


class RunnerStartFactory(factory.Factory):
    """Factory for creating RunnerStart instances."""

    class Meta:
        """Meta class for RunnerStart.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerStart

    event = "runner_start"
    flavor = factory.Faker("word")
    workflow = factory.Faker("sentence")
    repo = factory.Faker("word")
    github_event = factory.Faker("word")
    idle = factory.Faker("random_number", digits=2)
    queue_duration = factory.Faker("random_number", digits=2, min=0)


class CodeInformationFactory(factory.Factory):
    """Factory for creating CodeInformation instances."""

    class Meta:
        """Meta class for CodeInformation.

        Attributes:
            model: The metadata reference model.
        """

        model = CodeInformation

    code = factory.Faker("random_int", min=100, max=599)


class RunnerStopFactory(EventFactory):
    """Factory for creating RunnerStop instances."""

    class Meta:
        """Meta class for RunnerStop.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerStop

    event = "runner_stop"
    flavor = factory.Faker("word", ext_word_list=["large", "xlarge"])
    workflow = factory.Faker("sentence", nb_words=3)
    repo = factory.Faker("word")
    github_event = factory.Faker("word")
    status = factory.Faker("sentence", nb_words=5)
    status_info = factory.SubFactory(CodeInformationFactory)
    job_duration = factory.Faker("random_int", min=1, max=3600)
    job_conclusion = factory.Faker("word", ext_word_list=["success", "failure", "cancelled"])


class PreJobMetricsFactory(factory.Factory):
    """Factory for creating PreJobMetrics instances."""

    class Meta:
        """Meta class for PreJobmetrics.

        Attributes:
            model: The metadata reference model.
        """

        model = PreJobMetrics

    timestamp = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    workflow = factory.Faker("word")
    workflow_run_id = factory.Faker("uuid4")
    repository = factory.LazyFunction(
        lambda: f"{secrets.choice(['owner1', 'owner2'])}/{secrets.choice(['repo1', 'repo2'])}"
    )
    event = factory.Faker("word")


class PostJobMetricsFactory(factory.Factory):
    """Factory for creating PostJobMetrics instances."""

    class Meta:
        """Meta class for PostJobMetrics.

        Attributes:
            model: The metadata reference model.
        """

        model = PostJobMetrics

    timestamp = factory.LazyFunction(lambda: int(datetime.now().timestamp()))
    status = "normal"
    status_info = factory.SubFactory(CodeInformationFactory)


class PulledMetricsFactory(factory.Factory):
    """Factory for creating PulledMetrics instance."""

    class Meta:
        """Meta class for RunnerStop.

        Attributes:
            model: The metadata reference model.
        """

        model = PulledMetrics

    instance = OpenstackInstanceFactory()
    runner_installed_timestamp = datetime.now().timestamp()
    pre_job = PreJobMetricsFactory()
    post_job = PostJobMetricsFactory()


@dataclass
class _RunnerMetricsAble:
    """Dataclass compatible with RunnerMetrics protocol data structure.

    Attributes:
        metadata: The metadata of the VM in which the metrics are fetched from.
        instance_id: The instance ID of the VM in which the metrics are fetched from.
        installation_start_timestamp: The UNIX timestamp of in which the VM setup started.
        installation_end_timestamp: The UNIX timestamp of in which the VM setup ended.
        pre_job: The metrics for the pre-job phase.
        post_job: The metrics for the post-job phase.
    """

    pre_job: PreJobMetrics | None
    post_job: PostJobMetrics | None
    metadata: RunnerMetadata
    instance_id: InstanceID
    installation_start_timestamp: NonNegativeFloat
    installation_end_timestamp: NonNegativeFloat | None


class RunnerMetricsFactory(factory.Factory):
    """Factory for creating RunnerMetrics conformant dataclass."""

    class Meta:
        """Meta class for RunnerStop.

        Attributes:
            model: The metadata reference model.
        """

        model = _RunnerMetricsAble

    pre_job: PreJobMetrics | None = PreJobMetricsFactory()
    post_job: PostJobMetrics | None = PostJobMetricsFactory()
    metadata = RunnerMetadataFactory()
    instance_id = InstanceIDFactory()
    installation_start_timestamp = datetime.now().timestamp()
    installation_end_timestamp: float | None = datetime.now().timestamp() + 3
