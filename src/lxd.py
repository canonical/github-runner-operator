# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""LXD client interface.

The Lxd class is intend to be layer of abstraction to isolate the underlying implementation of LXD.
"""
from __future__ import annotations

import io
import tempfile
from subprocess import CalledProcessError  # nosec B404
from typing import IO, Optional, Tuple, Union

import pylxd.models

from errors import LxdError
from lxd_type import LxdInstanceConfig, ResourceProfileConfig, ResourceProfileDevices
from utilities import execute_command, secure_run_subprocess


class LxdInstanceFiles:
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

    def put(self, filename: str, content: Union[str, bytes], mode: Optional[int] = None) -> None:
        """Put a file with the given content in the LXD instance.

        Args:
            filename: Name of the file path.
            content: Content of the file.
            mode: File permission setting.

        Raises:
            LxdException: Unable to load the file into the LXD instance.
        """
        if isinstance(content, str):
            content = content.encode()

        with tempfile.NamedTemporaryFile() as file:
            file.write(content)
            lxc_cmd = [
                "/snap/bin/lxc",
                "file",
                "push",
                file.name,
                f"{self.instance.name}/{filename.lstrip('/')}",
            ]
            if mode:
                lxc_cmd += ["--mode", str(mode)]
            try:
                execute_command(lxc_cmd)
            except CalledProcessError as err:
                raise LxdError(
                    f"Unable to push file into LXD instance {self.instance.name}"
                ) from err


class LxdInstance:
    """A LXD instance.

    Attrs:
        name (str): Name of LXD instance.
        files (LxdInstanceFiles): Manager for the files on the LXD instance.
        status (str): Status of the LXD instance.
    """

    def __init__(self, name: str, pylxd_instance: pylxd.models.Instance):
        """Construct the LXD instance representation.

        Args:
            pylxd_instance: Instance of pylxd.models.Instance for the LXD instance.
        """
        self.name = name
        self._pylxd_instance = pylxd_instance
        self.files = LxdInstanceFiles(self._pylxd_instance)

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
            raise LxdError(f"Unable to stop LXD instance {self.name}") from err

    def execute(self, cmd: list[str], cwd: Optional[str] = None) -> Tuple[int, IO, IO]:
        """Execute a command within the LXD instance.

        Exceptions are not raise if command execution failed. Caller should check the exit code and
        stderr for failures.

        Args:
            cmd: Commands to be executed.
            cwd: Working directory to execute the commands.

        Returns:
            Tuple containing the exit code, stdout, stderr.
        """
        lxc_cmd = ["/snap/bin/lxc", "exec", self.name]
        if cwd:
            lxc_cmd += ["--cwd", cwd]

        lxc_cmd += ["--"] + cmd

        result = secure_run_subprocess(lxc_cmd)
        return (result.returncode, io.BytesIO(result.stdout), io.BytesIO(result.stderr))


class LxdInstances:
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
            return [
                LxdInstance(instance.name, instance)
                for instance in self._pylxd_client.instances.all()
            ]
        except pylxd.exceptions.LXDAPIException as err:
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
            return LxdInstance(config["name"], pylxd_instance)
        except pylxd.exceptions.LXDAPIException as err:
            raise LxdError(f"Unable to create LXD instance {config['name']}") from err


class LxdProfiles:
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
            raise LxdError(f"Unable to check if LXD profile {name} exists") from err

    def create(
        self, name: str, config: ResourceProfileConfig, devices: ResourceProfileDevices
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
            raise LxdError(f"Unable to create LXD profile {name} exists") from err


# Disable pylint as this class intends to mirror pylxd.
class Lxd:  # pylint: disable=too-few-public-methods
    """LXD client."""

    def __init__(self):
        """Construct the LXD client."""
        pylxd_client = pylxd.Client()
        self.instances = LxdInstances(pylxd_client)
        self.profiles = LxdProfiles(pylxd_client)
