# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing the main classes for business logic."""

import secrets
from dataclasses import dataclass

INSTANCE_SUFFIX_LENGTH = 12


@dataclass(eq=True, frozen=True)
class InstanceID:
    """Main identifier for a runner instance among all clouds and GitHub.

    The name attribute of this class must be compatible with all cloud providers and
    also with GitHub. The InstanceID is a fundamental concept in the github-runner
    that allows to correlate GitHub runners and the cloud runners. The InstanceID
    also allow to identify runners that are for this manager (this application unit
    when deployed with a charm), and also correlates metrics with runners.


    Attributes:
        name: Name of the instance to use.
        prefix: Prefix corresponding to the application (charm application unit).
        reactive: Identifies if the runner is reactive.
        suffix: Random suffix for the InstanceID.
    """

    prefix: str
    reactive: bool
    suffix: str

    @property
    def name(self) -> str:
        """Returns the name of the instance.

        Returns:
           Name of the instance
        """
        # Having a not number as a separator is ok, as the prefix should end
        # with a number (it is the unit number).
        return f"{self.prefix}{'r' if self.reactive else '-'}{self.suffix}"

    @classmethod
    def build_from_name(cls, prefix: str, name: str) -> "InstanceID":
        """Recreates an InstanceID from a string (name) and the application prefix.

        Args:
           prefix: Prefix for the application (unit name in the charm).
           name: Name of the instance.

        Raises:
           ValueError: If the name does not match the prefix.

        Returns:
           The InstanceID object.
        """
        if InstanceID.name_has_prefix(prefix, name):
            suffix = name.removeprefix(f"{prefix}")
        else:
            raise ValueError(f"Invalid runner name {name} for prefix {prefix}")

        # The separator from prefix and suffix indicates whether the runner is reactive.
        reactive = False
        separator = suffix[:1]
        if separator == "r":
            reactive = True
        suffix = suffix[1:]

        return cls(
            prefix=prefix,
            reactive=reactive,
            suffix=suffix,
        )

    @classmethod
    def build(cls, prefix: str, reactive: bool = False) -> "InstanceID":
        r"""Generate an InstanceID for a runner.

        It should be valid for all the CloudProviders and GitHub.

        The GitHub runner name convention is as following:
        A valid runner name is 64 characters or less in length and does not include '"', '/', ':',
        '<', '>', '\', '|', '*' and '?'.

        The collision rate calculation:
        alphanumeric 12 chars long (26 alphabet + 10 digits = 36)
        36^12 is big enough for our use-case.

        Args:
           prefix: Prefix for the InstanceID.
           reactive: If the instance ID to generate is a reactive runner.

        Returns:
            Instance ID of the runner.
        """
        suffix = secrets.token_hex(INSTANCE_SUFFIX_LENGTH // 2)
        return cls(prefix=prefix, reactive=reactive, suffix=suffix)

    @staticmethod
    def name_has_prefix(prefix: str, name: str) -> bool:
        """Check if a runner correspond to a prefix.

        The prefix must end with a number (it should be a unit name).

        Args:
           prefix: Application prefix (unit name of the charm).
           name: Name of the runner instance.

        Returns:
           True if the instance name is part the applicatoin with the prefix.
        """
        if name.startswith(prefix):
            suffix = name.removeprefix(f"{prefix}")
            if suffix[:1] in ("-", "r"):
                return True
        return False

    def __str__(self) -> str:
        """Return the name of the instance.

        Returns:
            Name of the instance.
        """
        return self.name

    def __repr__(self) -> str:
        """Representation of the InstanceID.

        Returns:
            String with the representation of the InstanceID.
        """
        return f"InstanceID({self.name!r})"
