# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""TODO."""

import secrets
from dataclasses import dataclass


@dataclass(eq=True, frozen=True)
class InstanceID:
    """TODO.

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
        return f"{self.prefix}-{self.suffix}"

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
        if name.startswith(prefix):
            suffix = name.removeprefix(f"{prefix}-")
        else:
            # TODO should we raise if invalid name?
            raise ValueError(f"Invalid runner name {name} for prefix {prefix}")

        return cls(
            prefix=prefix,
            reactive=False,
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
        suffix = secrets.token_hex(6)

        return cls(prefix=prefix, reactive=reactive, suffix=suffix)

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
