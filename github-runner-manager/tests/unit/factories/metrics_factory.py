# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for Metrics objects."""

import factory

from github_runner_manager.manager.cloud_runner_manager import CodeInformation
from github_runner_manager.metrics.events import Event, RunnerInstalled, RunnerStop


class EventFactory(factory.Factory):
    """Factory for creating Event instances."""

    class Meta:
        """Meta class for RunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = Event

    timestamp = factory.Faker("unix_time", end_datetime="now")
    event = factory.LazyAttribute(lambda obj: obj.__class__.__name__.lower())


class RunnerInstalledFactory(EventFactory):
    """Factory for creating RunnerInstalled instances."""

    class Meta:
        """Meta class for RunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerInstalled

    flavor = factory.Faker("word", ext_word_list=["large", "xlarge"])
    duration = factory.Faker("random_int", min=1, max=3600)


class CodeInformationFactory(factory.Factory):
    """Factory for creating CodeInformation instances."""

    class Meta:
        """Meta class for RunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = CodeInformation

    code = factory.Faker("random_int", min=100, max=599)  # Status code in the rang


class RunnerStopFactory(EventFactory):
    """Factory for creating RunnerStop instances."""

    class Meta:
        """Meta class for RunnerInstance.

        Attributes:
            model: The metadata reference model.
        """

        model = RunnerStop

    flavor = factory.Faker("word", ext_word_list=["large", "xlarge"])
    workflow = factory.Faker("sentence", nb_words=3)
    repo = factory.Faker("word")
    github_event = factory.Faker("word")
    status = factory.Faker("sentence", nb_words=5)
    status_info = factory.SubFactory(CodeInformationFactory)
    job_duration = factory.Faker("random_int", min=1, max=3600)
    job_conclusion = factory.Faker("word", ext_word_list=["success", "failure", "cancelled"])
