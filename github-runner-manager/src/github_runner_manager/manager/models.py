# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""TODO."""

import secrets
from dataclasses import dataclass

INSTANCE_SUFFIX_LENGTH = 12


@dataclass(eq=True, frozen=True)
class InstanceID:
    """TODO.

    This class needs to add compatibility for all cloud providers and GitHub.

    Attributes:
        name: TODO
        prefix: TODO
        reactive: TODO
        suffix: TODO
    """

    prefix: str
    reactive: bool
    suffix: str

    @property
    def name(self) -> str:
        """TODO.

        Returns:
           TODO
        """
        # Having a not number as a separator is good, as the prefix should end
        # with a number (it is the unit number).
        return f"{self.prefix}{'r' if self.reactive else '-'}{self.suffix}"

    @classmethod
    def build_from_name(cls, prefix: str, name: str) -> "InstanceID":
        """TODO.

        Args:
           prefix: TODO
           name: TODO

        Raises:
           ValueError: TODO

        Returns:
           TODO
        """
        if InstanceID.name_has_prefix(prefix, name):
            suffix = name.removeprefix(f"{prefix}")
        else:
            # TODO should we raise if invalid name?
            raise ValueError(f"Invalid runner name {name} for prefix {prefix}")

        # The separator from prefix and suffix may indicate if the runner is reactive.
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
        r"""Generate an intance_id to name a runner.

        It should be valid for all the CloudProviders and GitHub.

        The GitHub runner name convention is as following:
        A valid runner name is 64 characters or less in length and does not include '"', '/', ':',
        '<', '>', '\', '|', '*' and '?'.

        The collision rate calculation:
        alphanumeric 12 chars long (26 alphabet + 10 digits = 36)
        36^12 is big enough for our use-case.

        Args:
           prefix: TODO
           reactive: TODO

        Returns:
            Instance ID of the runner.
        """
        suffix = secrets.token_hex(INSTANCE_SUFFIX_LENGTH // 2)
        return cls(prefix=prefix, reactive=reactive, suffix=suffix)

    @staticmethod
    def name_has_prefix(prefix: str, name: str) -> bool:
        """TODO.

        TODO THIS CHECKS THE DIFFERENCE BETWEEN
        name-1-suffix
        and
        namd-11-suffix
        that is a bug in many places now.

        name-11 is not a name in the prefix name-11

        Args:
           prefix: TODO
           name: TODO

        Returns:
           TODO
        """
        if name.startswith(prefix):
            suffix = name.removeprefix(f"{prefix}")
            if suffix[:1] in ("-", "r"):
                return True
        return False

    def __str__(self) -> str:
        """TODO.

        Returns:
            TODO.
        """
        return self.name

    def __repr__(self) -> str:
        """TODO.

        Returns:
            TODO.
        """
        return f"InstanceID({self.name!r})"
