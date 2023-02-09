# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Mock for testing.

TODO:
    Rewrite the mock when the test are rewritten with pytest and interfaces
of Ghapi, pylxd, and request modules.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

import pylxd

from errors import RunnerError
from github_type import RegisterToken, RunnerApplication
from runner import LxdInstanceConfig

# Compressed tar file for testing.
# Python `tarfile` module works on only files.
# Hardcoding a sample tar file is simpler.
TEST_BINARY = (
    b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\xed\xd1\xb1\t\xc30\x14\x04P\xd5\x99B\x13\x04\xc9"
    b"\xb6\xacyRx\x01[\x86\x8c\x1f\x05\x12HeHaB\xe0\xbd\xe6\x8a\x7f\xc5\xc1o\xcb\xd6\xae\xed\xde"
    b"\xc2\x89R7\xcf\xd33s-\xe93_J\xc8\xd3X{\xa9\x96\xa1\xf7r\x1e\x87\x1ab:s\xd4\xdb\xbe\xb5\xdb"
    b"\x1ac\xcfe=\xee\x1d\xdf\xffT\xeb\xff\xbf\xfcz\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00_{\x00"
    b"\xc4\x07\x85\xe8\x00(\x00\x00"
)


class MockPylxdClient:
    """Mock the behavior of the pylxd client."""

    def __init__(self):
        self.instances = MockPylxdInstances()
        self.profiles = MockPylxdProfiles()


class MockPylxdInstances:
    """Mock the behavior of the pylxd Instances."""

    def __init__(self):
        self.instances = {}

    def create(self, config: LxdInstanceConfig, wait: bool = False) -> MockPylxdInstance:
        self.instances[config["name"]] = MockPylxdInstance(config["name"])
        return self.instances[config["name"]]

    def get(self, name: str):
        return self.instances[name]

    def all(self):
        return [i for i in self.instances.values() if not i.deleted]


class MockPylxdProfiles:
    """Mock the behavior of the pylxd Profiles."""

    def __init__(self):
        self.profiles = set()

    def create(self, name: str, config: dict[str, str], devices: dict[str, str]):
        self.profiles.add(name)

    def exists(self, name) -> bool:
        return name in self.profiles


class MockPylxdInstance:
    """Mock the behavior of a pylxd Instance."""

    def __init__(self, name: str):
        self.name = name
        self.status = "Stopped"
        self.deleted = False

        self.files = MockPylxdInstanceFiles()

    def start(self, wait: bool = True, timeout: int = 60):
        self.status = "Running"

    def stop(self, wait: bool = True, timeout: int = 60):
        self.status = "Stopped"

    def delete(self, wait: bool = True, timeout: int = 60):
        self.deleted = True

    def execute(self, cmd: Sequence[str]) -> tuple[int, str, str]:
        return 0, "", ""


class MockPylxdInstanceFiles:
    """Mock the behavior of a pylxd Instance files."""

    def __init__(self):
        pass

    def mk_dir(self, path, mode=None, uid=None, gid=None):
        pass

    def put(self, filepath, data, mode=None, uid=None, gid=None):
        pass


class MockErrorResponse:
    """Mock of an error response for request library."""

    def __init__(self):
        self.status_code = 200

    def json(self):
        return {"metadata": {"err": "test error"}}


def mock_pylxd_error_func(*arg, **kargs):
    raise pylxd.exceptions.LXDAPIException(MockErrorResponse())


def mock_runner_error_func(*arg, **kargs):
    raise RunnerError("test error")


class MockGhapiClient:
    """Mock for Ghapi client."""

    def __init__(self, token: str):
        self.token = token
        self.actions = MockGhapiActions()


class MockGhapiActions:
    """Mock for actions in Ghapi client."""

    def __init__(self):
        hash = hashlib.sha256()
        hash.update(TEST_BINARY)
        self.test_hash = hash.hexdigest()

    def _list_runner_applications(self):
        runners = []
        runners.append(
            RunnerApplication(
                os="linux",
                architecture="x64",
                download_url="https://www.example.com",
                filename="test_runner_binary",
                sha256_checksum=self.test_hash,
            )
        )
        return runners

    def list_runner_applications_for_repo(self, owner: str, repo: str):
        return self._list_runner_applications()

    def list_runner_application_for_org(self, org: str):
        return self._list_runner_applications()

    def create_registration_token_for_repo(self, owner: str, repo: str):
        return RegisterToken({"token": "test registration token"})

    def create_registration_token_for_org(self, org: str):
        return RegisterToken({"token": "test registration token"})

    def list_self_hosted_runners_for_repo(self, owner: str, repo: str):
        return {"runners": []}

    def list_self_hosted_runners_for_org(self, org: str):
        return {"runners": []}

    def delete_self_hosted_runner_from_repo(self, owner: str, repo: str, runner_id: str):
        pass

    def delete_self_hosted_runner_from_org(self, org: str, runner_id: str):
        pass
