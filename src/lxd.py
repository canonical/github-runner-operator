# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Low-level LXD client interface.

The LxdClient class offers a low-level interface to isolate the underlying
implementation of LXD.
"""
from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import IO, Any, Optional, Tuple, Union

import pylxd.models

from errors import LxdError, SubprocessError
from lxd_type import (
    LxdInstanceConfig,
    LxdNetwork,
    LxdResourceProfileConfig,
    LxdResourceProfileDevices,
    LxdStoragePoolConfiguration,
)
from utilities import execute_command, secure_run_subprocess

LXC_BINARY = "/snap/bin/lxc"

logger = logging.getLogger(__name__)


class LxdInstanceFileManager:
    """File manager of an LXD instance.

    Attributes:
        instance (LxdInstance): LXD instance where the files are located in.
    """

    def __init__(self, instance: LxdInstance):
        """Instantiate the file manager.

        Args:
            instance: LXD instance where the files are located in.
        """
        self.instance = instance

    def mk_dir(self, dir_name: str) -> None:
        """Create a directory in the LXD instance.

        Args:
            dir_name: Name of the directory to create.
        """
        self.instance.execute(["/usr/bin/mkdir", "-p", dir_name])

    def push_file(self, source: str, destination: str, mode: Optional[str] = None) -> None:
        """Push a file to the LXD instance.

        Args:
            source: Path of the file to push to the LXD instance.
            destination: Path in the LXD instance to load the file.
            mode: File permissions.

        Raises:
            LxdError: Unable to load the file into the LXD instance.
        """
        lxc_cmd = [
            LXC_BINARY,
            "file",
            "push",
            "--create-dirs",
            source,
            f"{self.instance.name}/{destination.lstrip('/')}",
        ]

        if mode:
            lxc_cmd += ["--mode", mode]

        try:
            execute_command(lxc_cmd)
        except SubprocessError as err:
            logger.exception("Failed to push file")
            raise LxdError(
                f"Unable to push file into the LXD instance {self.instance.name}"
            ) from err

    def write_file(
        self, filepath: str, content: Union[str, bytes], mode: Optional[str] = None
    ) -> None:
        """Write a file with the given content into the LXD instance.

        Args:
            filepath: Path in the LXD instance to load the file.
            content: Content of the file.
            mode: File permission setting.

        Raises:
            LxdError: Unable to load the file to the LXD instance.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        with tempfile.NamedTemporaryFile() as file:
            file.write(content)
            file.flush()

            try:
                self.push_file(file.name, filepath, mode)
            # 2024/04/02 - We should define a new error, wrap it and re-raise it.
            except LxdError:  # pylint: disable=try-except-raise
                raise

    def pull_file(self, source: str, destination: str, is_dir: bool = False) -> None:
        """Pull a file from the LXD instance to the local machine.

        Args:
            source: Path of the file to pull in the LXD instance.
            destination: Path in local machine.
            is_dir: Whether the source is a directory.

        Raises:
            LxdError: Unable to load the file from the LXD instance.
        """
        lxc_cmd = [
            LXC_BINARY,
            "file",
            "pull",
            *(["-r"] if is_dir else []),
            f"{self.instance.name}/{source.lstrip('/')}",
            destination,
        ]

        try:
            execute_command(lxc_cmd)
        except SubprocessError as err:
            logger.exception("Failed to pull file")
            raise LxdError(
                f"Unable to pull file {source} from the LXD instance {self.instance.name}"
            ) from err

    def read_file(self, filepath: str) -> str:
        """Read the content of a file in the LXD instance.

        Args:
            filepath: Path of the file in the LXD instance.

        Raises:
            LxdError: Unable to load the file from the LXD instance.

        Returns:
            The content of the file.
        """
        with tempfile.NamedTemporaryFile() as file:
            try:
                self.pull_file(filepath, file.name)
            # 2024/04/02 - We should define a new error, wrap it and re-raise it.
            except LxdError:  # pylint: disable=try-except-raise
                raise

            return file.read().decode("utf-8")


class LxdInstance:
    """An LXD instance.

    Attributes:
        name (str): Name of the LXD instance.
        files (LxdInstanceFiles): Manager for the files on the LXD instance.
        status (str): Status of the LXD instance.
    """

    def __init__(self, pylxd_instance: pylxd.models.Instance):
        """Instantiate the LXD instance representation.

        Args:
            pylxd_instance: Instance of pylxd.models.Instance for the LXD
                instance.
        """
        self._pylxd_instance = pylxd_instance
        self.name = self._pylxd_instance.name
        self.files = LxdInstanceFileManager(self)

    @property
    def status(self) -> str:
        """Status of the LXD instance.

        Returns:
            Status of the LXD instance.
        """
        return self._pylxd_instance.status

    def start(self, timeout: int = 30, force: bool = True, wait: bool = False) -> None:
        """Start the LXD instance.

        Args:
            timeout: Timeout for starting the LXD instance.
            force: Whether to force start the LXD instance.
            wait: Whether to wait until the LXD instance is started before
                returning.

        Raises:
            LxdError: Unable to start the LXD instance.
        """
        try:
            self._pylxd_instance.start(timeout, force, wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to start the LXD instance")
            raise LxdError(f"Unable to start the LXD instance {self.name}") from err

    def stop(self, timeout: int = 30, force: bool = True, wait: bool = False) -> None:
        """Stop the LXD instance.

        Args:
            timeout: Timeout for stopping the LXD instance.
            force: Whether to force stop the LXD instance.
            wait: Whether to wait until the LXD instance is stopped before
                returning.

        Raises:
            LxdError: Unable to stop the LXD instance.
        """
        try:
            self._pylxd_instance.stop(timeout, force, wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to stop the LXD instance")
            raise LxdError(f"Unable to stop the LXD instance {self.name}") from err

    def delete(self, wait: bool = False) -> None:
        """Delete the LXD instance.

        Args:
            wait: Whether to wait until the LXD instance is stopped before
                returning.

        Raises:
            LxdError: Unable to delete the LXD instance.
        """
        try:
            self._pylxd_instance.delete(wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to delete the LXD instance")
            raise LxdError(f"Unable to delete the LXD instance {self.name}") from err

    def execute(
        self, cmd: list[str], cwd: Optional[str] = None, hide_cmd: bool = False, **kwargs: Any
    ) -> Tuple[int, IO, IO]:
        """Execute a command within the LXD instance.

        Exceptions are not raised if command execution failed. Caller should
        check the exit code and stderr for errors.

        The command is executed with `subprocess.run`, additional arguments can be passed to it as
        keyword arguments. The following arguments to `subprocess.run` should not be set:
        `capture_output`, `shell`, `check`. As those arguments are used by this function.

        Args:
            cmd: Commands to be executed.
            cwd: Working directory to execute the commands.
            hide_cmd: Hide logging of cmd.
            kwargs: Additional keyword arguments for the `subprocess.run` call.


        Returns:
            Tuple containing the exit code, stdout, stderr.
        """
        lxc_cmd = [LXC_BINARY, "exec", self.name]
        if cwd:
            lxc_cmd += ["--cwd", cwd]

        lxc_cmd += ["--"] + cmd

        result = secure_run_subprocess(lxc_cmd, hide_cmd, **kwargs)
        return (result.returncode, io.BytesIO(result.stdout), io.BytesIO(result.stderr))


class LxdInstanceManager:
    """LXD instance manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Instantiate the LXD instance manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def all(self) -> list[LxdInstance]:
        """Get list of LXD instances.

        Raises:
            LxdError: Unable to get all LXD instances.

        Returns:
            List of LXD instances.
        """
        try:
            return [LxdInstance(instance) for instance in self._pylxd_client.instances.all()]
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to get all LXD instances")
            raise LxdError("Unable to get all LXD instances") from err

    def create(self, config: LxdInstanceConfig, wait: bool) -> LxdInstance:
        """Create an LXD instance.

        Args:
            config: Configuration for the LXD instance.
            wait: Whether to wait until the LXD instance is created before
                returning.

        Raises:
            LxdError: Unable to get all LXD instances.

        Returns:
            The created LXD instance.
        """
        try:
            pylxd_instance = self._pylxd_client.instances.create(config=config, wait=wait)
            return LxdInstance(pylxd_instance)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to create the LXD instance")
            raise LxdError(f"Unable to create the LXD instance {config['name']}") from err


class LxdProfileManager:
    """LXD profile manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Instantiate the LXD profile manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def exists(self, name: str) -> bool:
        """Check whether an LXD profile of a given name exists.

        Args:
            name: Name for LXD profile to check.

        Raises:
            LxdError: Unable to check the LXD profile existence.

        Returns:
            Whether the LXD profile of the given name exists.
        """
        try:
            return self._pylxd_client.profiles.exists(name)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to check if LXD profile exists")
            raise LxdError(f"Unable to check if LXD profile {name} exists") from err

    def create(
        self, name: str, config: LxdResourceProfileConfig, devices: LxdResourceProfileDevices
    ) -> None:
        """Create an LXD profile.

        Args:
            name: Name of the LXD profile to create.
            config: Configuration of the LXD profile.
            devices: Devices configuration of the LXD profile.

        Raises:
            LxdError: Unable to create the LXD profile.
        """
        try:
            self._pylxd_client.profiles.create(name, config, devices)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to create LXD profile")
            raise LxdError(f"Unable to create LXD profile {name}") from err

    def get(self, name: str) -> LxdProfile:
        """Get an LXD profile.

        Args:
            name: Name of the LXD profile.

        Raises:
            LxdError: Unable to get the LXD profile with the name.

        Returns:
            LXDProfile with given name.
        """
        try:
            return self._pylxd_client.profiles.get(name)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to get LXD profile")
            raise LxdError(f"Unable to get LXD profile {name}") from err


class LxdProfile:
    """LXD profile."""

    def __init__(
        self,
        pylxd_profile: pylxd.models.Profile,
    ):
        """Instantiate the LXD profile.

        Args:
            pylxd_profile: Instance of the pylxd.models.Profile.
        """
        self._pylxd_profile = pylxd_profile

        self.name = self._pylxd_profile.name
        self.description = self._pylxd_profile.description
        self.config = self._pylxd_profile.config
        self.devices = self._pylxd_profile.devices
        self.used_by = self._pylxd_profile.used_by

    def save(self) -> None:
        """Save the current configuration of profile."""
        self._pylxd_profile.config = self.config
        self._pylxd_profile.save()

    def delete(self) -> None:
        """Delete the profile."""
        self._pylxd_profile.delete()


# Disable pylint as public method number check as this class can be extended in the future.
class LxdNetworkManager:  # pylint: disable=too-few-public-methods
    """LXD network manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Instantiate the LXD profile manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def get(self, name: str) -> LxdNetwork:
        """Get the LXD network information.

        Args:
            name: The name of the LXD network.

        Returns:
            Information on the LXD network.
        """
        network = self._pylxd_client.networks.get(name)
        return LxdNetwork(
            network.name,
            network.description,
            network.type,
            network.config,
            network.managed,
            network.used_by,
        )


class LxdStoragePoolManager:
    """LXD storage pool manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Instantiate the LXD storage pool manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def all(self) -> list[LxdStoragePool]:
        """Get all LXD storage pool.

        Returns:
            List of LXD storage pools.
        """
        return [LxdStoragePool(pool) for pool in self._pylxd_client.storage_pools.all()]

    def get(self, name: str) -> LxdStoragePool:
        """Get an LXD storage pool.

        Args:
            name: Name of the storage pool.

        Raises:
            LxdError: If the storage pool with given name was not found.

        Returns:
            The LXD storage pool.
        """
        try:
            return LxdStoragePool(self._pylxd_client.storage_pools.get(name))
        except pylxd.exceptions.NotFound as err:
            logger.exception("LXD storage pool not found")
            raise LxdError(f"LXD storage pool {name} not found") from err

    def exists(self, name: str) -> bool:
        """Check if an LXD storage pool exists.

        Args:
            name: Name to check for.

        Returns:
            Whether the storage pool exists.
        """
        return self._pylxd_client.storage_pools.exists(name)

    def create(self, config: LxdStoragePoolConfiguration) -> LxdStoragePool:
        """Create an LXD storage pool.

        Args:
            config: Configuration for the storage pool.

        Returns:
            The LXD storage pool.
        """
        return self._pylxd_client.storage_pools.create(config)


class LxdStoragePool:
    """An LXD storage pool.

    Attributes:
        name (str): Name of the storage pool.
        driver (str): Type of driver of the storage pool.
        used_by (list[str]): LXD instances using the storage pool.
        config (dict[str, any]): Dictionary of the configuration of the
            storage pool.
        managed (bool): Whether LXD manages the storage pool.
    """

    def __init__(
        self,
        pylxd_storage_pool: pylxd.models.StoragePool,
    ):
        """Instantiate the LXD storage pool.

        Args:
            pylxd_storage_pool: Instance of the pylxd.models.StoragePool.
        """
        self._pylxd_storage_pool = pylxd_storage_pool

        self.name = self._pylxd_storage_pool.name
        self.driver = self._pylxd_storage_pool.driver
        self.used_by = self._pylxd_storage_pool.used_by
        self.config = self._pylxd_storage_pool.config
        self.managed = self._pylxd_storage_pool.managed

    def save(self) -> None:
        """Save the current configuration of storage pool."""
        self._pylxd_storage_pool.config = self.config
        self._pylxd_storage_pool.save()

    def delete(self) -> None:
        """Delete the storage pool."""
        self._pylxd_storage_pool.delete()


class LxdImageManager:  # pylint: disable=too-few-public-methods
    """LXD image manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Instantiate the LXD image manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def create(self, name: str, path: Path) -> None:
        """Import a LXD image.

        Args:
            name: Alias for the image.
            path: Path of the LXD image file.

        Raises:
            LxdError: Unable to import the file as LXD image.
        """
        result = secure_run_subprocess(["lxc", "image", "import", "--alias", name, str(path)])
        if result.returncode != 0:
            raise LxdError(result.stdout.decode("utf-8"))


# Disable pylint as the public methods of this class are split into instances and profiles.
class LxdClient:  # pylint: disable=too-few-public-methods
    """LXD client."""

    def __init__(self) -> None:
        """Instantiate the LXD client."""
        pylxd_client = pylxd.Client()
        self.instances = LxdInstanceManager(pylxd_client)
        self.profiles = LxdProfileManager(pylxd_client)
        self.networks = LxdNetworkManager(pylxd_client)
        self.storage_pools = LxdStoragePoolManager(pylxd_client)
        self.images = LxdImageManager(pylxd_client)
