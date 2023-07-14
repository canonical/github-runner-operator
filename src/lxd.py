# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Low-level LXD client interface.

The LxdClient class offer a low-level interface isolate the underlying implementation of LXD.
"""
from __future__ import annotations

import logging
import tempfile
from typing import Optional, Tuple, Union

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

logger = logging.getLogger(__name__)


class LxdInstanceFileManager:
    """File manager of a LXD instance.

    Attrs:
        instance (LxdInstance): LXD instance where the files are located in.
    """

    def __init__(self, instance: LxdInstance):
        """Construct the file manager.

        Args:
            instance: LXD instance where the files are located in.
        """
        self.instance = instance

    def mk_dir(self, dir_name: str) -> None:
        """Create a directory in the LXD instance.

        Args:
            dir: Name of the directory to create.
        """
        self.instance.execute(["/usr/bin/mkdir", "-p", dir_name])

    def push_file(self, source: str, destination: str, mode: Optional[str] = None) -> None:
        """Push a file to the LXD instance.

        Args:
            source: Path of the file to push to the LXD instance.
            destination: Path in the LXD instance to load the file.
            mode: File permission setting.

        Raises:
            LxdException: Unable to load the file into the LXD instance.
        """
        lxc_cmd = [
            "/snap/bin/lxc",
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
            raise LxdError(f"Unable to push file into LXD instance {self.instance.name}") from err

    def write_file(
        self, filepath: str, content: Union[str, bytes], mode: Optional[str] = None
    ) -> None:
        """Write a file with the given content in the LXD instance.

        Args:
            filepath: Path in the LXD instance to load the file.
            content: Content of the file.
            mode: File permission setting.

        Raises:
            LxdException: Unable to load the file to the LXD instance.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        with tempfile.NamedTemporaryFile() as file:
            file.write(content)
            file.flush()

            self.push_file(file.name, filepath, mode)

    def pull_file(self, source: str, destination: str) -> None:
        """Pull a file from the LXD instance.

        Args:
            source: Path of the file to pull in the LXD instance.
            destination: Path of load the file.

        Raises:
            LxdException: Unable to load the file from the LXD instance.
        """
        lxc_cmd = [
            "/snap/bin/lxc",
            "file",
            "pull",
            f"{self.instance.name}/{source.lstrip('/')}",
            destination,
        ]

        try:
            execute_command(lxc_cmd)
        except SubprocessError as err:
            logger.exception("Failed to pull file")
            raise LxdError(
                f"Unable to pull file {source} from LXD instance {self.instance.name}"
            ) from err

    def read_file(self, filepath: str) -> str:
        """Read content of a file in the LXD instance.

        Args:
            filepath: Path of the file in the LXD instance.

        Raises:
            LxdException: Unable to load the file from the LXD instance.

        Returns:
            The content of the file.
        """
        with tempfile.NamedTemporaryFile() as file:
            self.pull_file(filepath, file.name)

            return file.read().decode("utf-8")


class LxdInstance:
    """A LXD instance.

    Attrs:
        name (str): Name of LXD instance.
        files (LxdInstanceFiles): Manager for the files on the LXD instance.
        status (str): Status of the LXD instance.
    """

    def __init__(self, pylxd_instance: pylxd.models.Instance):
        """Construct the LXD instance representation.

        Args:
            pylxd_instance: Instance of pylxd.models.Instance for the LXD instance.
        """
        self._pylxd_instance = pylxd_instance
        self.name = self._pylxd_instance.name
        self.files = LxdInstanceFileManager(self._pylxd_instance)

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
            wait: Whether to wait until the LXD instance started before returning.

        Raises:
            LxdException: Unable to start the LXD instance.
        """
        try:
            self._pylxd_instance.start(timeout, force, wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to start LXD instance")
            raise LxdError(f"Unable to start LXD instance {self.name}") from err

    def stop(self, timeout: int = 30, force: bool = True, wait: bool = False) -> None:
        """Stop the LXD instance.

        Args:
            timeout: Timeout for stopping the LXD instance.
            force: Whether to force stop the LXD instance.
            wait: Whether to wait until the LXD instance stopped before returning.

        Raises:
            LxdException: Unable to stop the LXD instance.
        """
        try:
            self._pylxd_instance.stop(timeout, force, wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to stop LXD instance")
            raise LxdError(f"Unable to stop LXD instance {self.name}") from err

    def delete(self, wait: bool = False) -> None:
        """Delete the LXD instance.

        Args:
            wait: Whether to wait until the LXD instance stopped before returning.

        Raises:
            LxdException: Unable to delete the LXD instance.
        """
        try:
            self._pylxd_instance.delete(wait)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to delete LXD instance")
            raise LxdError(f"Unable to delete LXD instance {self.name}") from err

    def execute(
        self, cmd: list[str], cwd: Optional[str] = None, hide_cmd: bool = False
    ) -> Tuple[int, str, str]:
        """Execute a command within the LXD instance.

        Exceptions are not raise if command execution failed. Caller should check the exit code and
        stderr for failures.

        Args:
            cmd: Commands to be executed.
            cwd: Working directory to execute the commands.
            hide_cmd: Hide logging of cmd.

        Returns:
            Tuple containing the exit code, stdout, stderr.
        """
        lxc_cmd = ["/snap/bin/lxc", "exec", self.name]
        if cwd:
            lxc_cmd += ["--cwd", cwd]

        lxc_cmd += ["--"] + cmd

        result = secure_run_subprocess(lxc_cmd, hide_cmd)
        return (result.returncode, result.stdout, result.stderr)


class LxdInstanceManager:
    """LXD instance manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Construct the LXD instance manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def all(self) -> list[LxdInstance]:
        """Get list of LXD instances.

        Raises:
            LxdException: Unable to get all LXD instance.

        Returns:
            List of LXD instances.
        """
        try:
            return [LxdInstance(instance) for instance in self._pylxd_client.instances.all()]
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to get all LXD instance")
            raise LxdError("Unable to get all LXD instances") from err

    def create(self, config: LxdInstanceConfig, wait: bool) -> LxdInstance:
        """Create a LXD instance.

        Args:
            config: Configuration for the LXD instance.
            wait: Whether to wait until the LXD instance created before returning.

        Raises:
            LxdException: Unable to get all LXD instance.

        Returns:
            The created LXD instance.
        """
        try:
            pylxd_instance = self._pylxd_client.instances.create(config=config, wait=wait)
            return LxdInstance(pylxd_instance)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to create LXD instance")
            raise LxdError(f"Unable to create LXD instance {config['name']}") from err


class LxdProfileManager:
    """LXD profile manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Construct the LXD profile manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def exists(self, name: str) -> bool:
        """Check whether a LXD profile of a given name exists.

        Args:
            name: Name for LXD profile to check.

        Raises:
            LxdException: Unable to check the LXD profile existence.

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
        """Create a LXD profile.

        Args:
            name: Name of the LXD profile to create.
            config: Configuration of the LXD profile.
            devices Devices configuration of the LXD profile.

        Raises:
            LxdException: Unable to create the LXD profile.
        """
        try:
            self._pylxd_client.profiles.create(name, config, devices)
        except pylxd.exceptions.LXDAPIException as err:
            logger.exception("Failed to create LXD profile")
            raise LxdError(f"Unable to create LXD profile {name}") from err


# Disable pylint as other method of this class can be extended in the future.
class LxdNetworkManager:  # pylint: disable=too-few-public-methods
    """LXD network manager."""

    def __init__(self, pylxd_client: pylxd.Client):
        """Construct the LXD profile manager.

        Args:
            pylxd_client: Instance of pylxd.Client.
        """
        self._pylxd_client = pylxd_client

    def get(self, name: str) -> LxdNetwork:
        """Get a LXD network information.

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
        """Construct the LXD storage pool manager.

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
        """Get a LXD storage pool.

        Args:
            name: Name of the storage pool.

        Returns:
            The LXD storage pool.
        """
        try:
            return LxdStoragePool(self._pylxd_client.storage_pools.get(name))
        except pylxd.exceptions.NotFound as err:
            logger.exception("LXD storage pool not found")
            raise LxdError(f"LXD storage pool {name} not found") from err

    def exists(self, name: str) -> bool:
        """Check if a LXD storage pool exists.

        Args:
            name: Name to check for.

        Returns:
            Whether the storage pool exists.
        """
        return self._pylxd_client.storage_pools.exists(name)

    def create(self, config: LxdStoragePoolConfiguration) -> LxdStoragePool:
        """Create a LXD storage pool.

        Args:
            config: Configuration for the storage pool.

        Returns:
            The LXD storage pool.
        """
        return self._pylxd_client.storage_pools.create(config)


class LxdStoragePool:
    """A LXD storage pool.

    Attrs:
        name (str): Name of the storage pool.
        driver (str): Type of driver of the storage pool.
        used_by (list[str]): LXD instance that uses the storage pool.
        config (dict[str, any]): Dictionary of the configuration of the storage pool.
        managed (bool): Whether LXD manages the storage pool.
    """

    def __init__(
        self,
        pylxd_storage_pool: pylxd.models.StoragePool,
    ):
        """Construct the LXD storage pool.

        Args:
            pylxd_storage_pool: Instance of the pylxd.models.StoragePool.
        """
        self._pylxd_storage_pool = pylxd_storage_pool

        self.name = self._pylxd_storage_pool.name
        self.driver = self._pylxd_storage_pool.driver
        self.used_by = self._pylxd_storage_pool.used_by
        self.config = self._pylxd_storage_pool.config
        self.managed = self._pylxd_storage_pool.managed

    def save(self):
        """Save the current configuration of storage pool."""
        self._pylxd_storage_pool.config = self.config
        self._pylxd_storage_pool.save()

    def delete(self):
        """Delete the storage pool."""
        self._pylxd_storage_pool.delete()


# Disable pylint as the public methods of this class in split into instances and profiles.
class LxdClient:  # pylint: disable=too-few-public-methods
    """LXD client."""

    def __init__(self):
        """Construct the LXD client."""
        pylxd_client = pylxd.Client()
        self.instances = LxdInstanceManager(pylxd_client)
        self.profiles = LxdProfileManager(pylxd_client)
        self.networks = LxdNetworkManager(pylxd_client)
        self.storage_pools = LxdStoragePoolManager(pylxd_client)
