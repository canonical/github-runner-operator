# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

# The factory definitions don't need public methods
# pylint: disable=too-few-public-methods

import random
from typing import Generic, TypeVar

import factory
import factory.fuzzy
from pydantic.networks import IPvAnyAddress

from charm_state import SSHDebugConnection

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
