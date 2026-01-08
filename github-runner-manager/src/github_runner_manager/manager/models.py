# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing the main classes for business logic."""

import secrets
from dataclasses import asdict, dataclass, field

INSTANCE_SUFFIX_LENGTH = 12


class InstanceIDInvalidError(Exception):
    """Raised when the InstanceID naming will break the provider of GitHub."""


@dataclass(eq=True, frozen=True, order=True)
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
    suffix: str
    reactive: bool | None = None

    @property
    def name(self) -> str:
        """Returns the name of the instance.

        Returns:
           Name of the instance
        """
        if self.reactive is True:
            runner_type = "r-"
        elif self.reactive is False:
            runner_type = "n-"
        else:
            runner_type = ""
        return f"{self.prefix}-{runner_type}{self.suffix}"

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
            suffix = name.removeprefix(f"{prefix}-")
        else:
            raise ValueError(f"Invalid runner name {name} for prefix {prefix}")

        # The separator from prefix and suffix indicates whether the runner is reactive.
        # To maintain backwards compatibility, if there is no r- or n- (reactive or
        # non-reactive), we assume non-reactive and keep the full suffix.
        reactive = None
        separator = suffix[:2]
        if separator == "r-":
            reactive = True
            suffix = suffix[2:]
        elif separator == "n-":
            reactive = False
            suffix = suffix[2:]

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

        Raises:
            InstanceIDInvalidError: If the instance name is not valid (too long).
        """
        suffix = secrets.token_hex(INSTANCE_SUFFIX_LENGTH // 2)
        instance_id = cls(prefix=prefix, reactive=reactive, suffix=suffix)
        # By default, for OpenStack with MySQL, the limit is 64 characters.
        if len(instance_id.name) > 64:
            raise InstanceIDInvalidError(
                f"InstanceID {instance_id.name} is too over 64 characters and can break "
                "OpenStack naming. You can try to make the application name shorter to fix it."
            )
        return instance_id

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
        if name.startswith(f"{prefix}-"):
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


@dataclass(order=True)
class RunnerMetadata:
    """Metadata linking a cloud runner to its GitHub runner.

    Attributes:
        runner_id: The GitHub runner ID.
    """

    runner_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        """Return the metadata as a dict for storage.

        Returns:
            Metadata as a dict with non-None values.
        """
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, str] | None) -> "RunnerMetadata":
        """Create RunnerMetadata from a dict, ignoring unknown fields.

        This handles backwards compatibility with VMs that have legacy fields
        like 'platform_name', 'url', or 'prefix' stored in their metadata.

        Args:
            data: Dictionary from OpenStack VM metadata.

        Returns:
            RunnerMetadata instance.
        """
        if not data:
            return cls()
        return cls(runner_id=data.get("runner_id"))


@dataclass(order=True)
class RunnerIdentity:
    """Identity for the runner.

    The full identity of the runner is made of the instance_id and the
    metadata. The instance_id is used for the name of the runner in the cloud
    provider, and it should be immutable. The metadata is used to identify the
    platform provider and other information that could be relevant to identify
    the runner in the platform provider.

    Attributes:
        instance_id: InstanceID of the runner.
        metadata: Metadata for the runner.
    """

    instance_id: InstanceID
    metadata: RunnerMetadata


@dataclass
class RunnerContext:
    """Information provided by the platform provider needed to spawn a runner.

    Attributes:
        shell_run_script: Script to run the platform agent.
        ingress_tcp_ports: Ports to be opened in the cloud provider.
    """

    shell_run_script: str
    ingress_tcp_ports: list[int] = field(default_factory=lambda: [])
