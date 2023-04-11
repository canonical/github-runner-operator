from __future__ import annotations

import io
import tempfile
from subprocess import CalledProcessError
from typing import IO, Optional, Union

import pylxd.models

from lxd_type import LxdException, LxdInstanceConfig, ResourceProfileConfig, ResourceProfileDevices
from utilities import execute_command, run_subprocess


class LxdInstanceFiles:
    def __init__(self, instance: LxdInstance):
        self.instance = instance

    def mk_dir(self, dir: str):
        self.instance.execute(["/usr/bin/mkdir", "-p", "dir"])

    def put(self, filename: str, content: Union[str, bytes], mode: Optional[int] = None):
        with tempfile.NamedTemporaryFile() as file:
            file.write(content)
            lxc_cmd = [
                "/usr/bin/lxc",
                "file",
                "push",
                file.name,
                f"{self.instance.name}/{filename}",
            ]
            if mode:
                lxc_cmd += ["--mode", str(mode)]
            try:
                execute_command(lxc_cmd)
            except CalledProcessError as err:
                raise LxdException(
                    f"Unable to push file into LXD instance {self.instance.name}"
                ) from err


class LxdInstance:
    def __init__(self, name: str, pylxd_instance: pylxd.models.Instance):
        self.name = name
        self.pylxd_instance = pylxd_instance
        self.files = LxdInstanceFiles(self.name)

    @property
    def status(self):
        self.pylxd_instance.status

    def start(self, timeout: int = 30, force: bool = True, wait: bool = False):
        try:
            self.pylxd_instance.start(timeout, force, wait)
        except pylxd.LXDAPIException as err:
            raise LxdException(f"Unable to start LXD instance {self.name}") from err

    def stop(self, timeout: int = 30, force: bool = True, wait: bool = False):
        try:
            self.pylxd_instance.stop(timeout, force, wait)
        except pylxd.LXDAPIException as err:
            raise LxdException(f"Unable to stop LXD instance {self.name}") from err

    def execute(self, cmd: list[str], cwd: Optional[str] = None) -> tuple(int, IO, IO):
        lxc_cmd = ["/snap/bin/lxc", "exec", self.name]
        if cwd:
            lxc_cmd += ["--cwd", cwd]
        lxc_cmd += ["--" + cmd]
        result = run_subprocess(lxc_cmd)
        return (result.returncode, io.StringIO(result.stdout), io.StringIO(result.stderr))


class LxdInstances:
    def __init__(self, pylxd_client: pylxd.Client):
        self.pylxd_client = pylxd_client

    def all(self) -> list[LxdInstance]:
        return [
            LxdInstance(instance.name, instance) for instance in self.pylxd_client.instances.all()
        ]

    def create(self, config: LxdInstanceConfig, wait: bool) -> LxdInstance:
        try:
            pylxd_instance = self.pylxd_client.instances.create(config=config, wait=wait)
            return LxdInstance(config["name"], pylxd_instance)
        except pylxd.LXDAPIException as err:
            raise LxdException(f"Unable to create LXD instance {config['name']}") from err


class LxdProfiles:
    def __init__(self, pylxd_client: pylxd.Client):
        self.pylxd_client = pylxd_client

    def exists(self, name: str) -> bool:
        try:
            self.pylxd_client.profiles.exists(name)
        except pylxd.LXDAPIException as err:
            raise LxdException(f"Unable to check if LXD profile {name} exists") from err

    def create(self, name: str, config: ResourceProfileConfig, devices: ResourceProfileDevices):
        try:
            self.pylxd_client.profiles.create(name, config, devices)
        except pylxd.LXDAPIException as err:
            raise LxdException(f"Unable to create LXD profile {name} exists") from err


class Lxd:
    def __init__(self):
        pylxd_client = pylxd.Client()
        self.instances = LxdInstances(pylxd_client)
        self.profiles = LxdProfiles(pylxd_client)
