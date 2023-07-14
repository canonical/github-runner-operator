# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Mock for testing."""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Optional, Sequence, Union

from errors import LxdError, RunnerError
from github_type import RegistrationToken, RemoveToken, RunnerApplication
from lxd_type import LxdNetwork
from runner import LxdInstanceConfig

logger = logging.getLogger(__name__)

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


class MockLxdClient:
    """Mock the behavior of the LXD client."""

    def __init__(self):
        self.instances = MockLxdInstanceManager()
        self.profiles = MockLxdProfileManager()
        self.networks = MockLxdNetworkManager()
        self.storage_pools = MockLxdStoragePoolManager()


class MockLxdInstanceManager:
    """Mock the behavior of the LXD Instances."""

    def __init__(self):
        self.instances = {}

    def create(self, config: LxdInstanceConfig, wait: bool = False) -> MockLxdInstance:
        self.instances[config["name"]] = MockLxdInstance(config["name"])
        return self.instances[config["name"]]

    def get(self, name: str):
        return self.instances[name]

    def all(self):
        return [i for i in self.instances.values() if not i.deleted]


class MockLxdProfileManager:
    """Mock the behavior of the LXD Profiles."""

    def __init__(self):
        self.profiles = set()

    def create(self, name: str, config: dict[str, str], devices: dict[str, str]):
        self.profiles.add(name)

    def exists(self, name) -> bool:
        return name in self.profiles


class MockLxdNetworkManager:
    """Mock the behavior of the LXD networks"""

    def __init__(self):
        pass

    def get(self, name: str) -> LxdNetwork:
        return LxdNetwork(
            "lxdbr0", "", "bridge", {"ipv4.address": "10.1.1.1/24"}, True, ("default")
        )


class MockLxdInstance:
    """Mock the behavior of a LXD Instance."""

    def __init__(self, name: str):
        self.name = name
        self.status = "Stopped"
        self.deleted = False

        self.files = MockLxdInstanceFileManager()

    def start(self, wait: bool = True, timeout: int = 60):
        self.status = "Running"

    def stop(self, wait: bool = True, timeout: int = 60):
        self.status = "Stopped"
        # Ephemeral virtual machine should be deleted on stop.
        self.deleted = True

    def delete(self, wait: bool = True):
        self.deleted = True

    def execute(
        self, cmd: Sequence[str], cwd: Optional[str] = None, hide_cmd: bool = False
    ) -> tuple[int, str, str]:
        return 0, "", ""


class MockLxdInstanceFileManager:
    """Mock the behavior of a LXD Instance files."""

    def __init__(self):
        self.files = {}

    def mk_dir(self, path):
        pass

    def push_file(self, source: str, destination: str, mode: Optional[str] = None):
        self.files[destination] = "mock_content"

    def write_file(self, filepath: str, data: Union[bytes, str], mode: Optional[str] = None):
        self.files[filepath] = data

    def read_file(self, filepath: str):
        return self.files.get(str(filepath), None)


class MockLxdStoragePoolManager:
    """Mock the behavior of LXD storage pools."""

    def __init__(self):
        self.pools = {}

    def all(self):
        return [pool for pool in self.pools.values() if not pool.delete]

    def get(self, name):
        return self.pools[name]

    def exists(self, name):
        if name in self.pools:
            return not self.pools[name].delete
        else:
            return False

    def create(self, config):
        self.pools[config["name"]] = MockLxdStoragePool()
        return self.pools[config["name"]]


class MockLxdStoragePool:
    """Mock the behavior of a LXD storage pool."""

    def __init__(self):
        self.delete = False

    def save(self):
        pass

    def delete(self):
        self.delete = True


class MockErrorResponse:
    """Mock of an error response for request library."""

    def __init__(self):
        self.status_code = 200

    def json(self):
        return {"metadata": {"err": "test error"}}


def mock_lxd_error_func(*arg, **kargs):
    raise LxdError(MockErrorResponse())


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
        self.registration_token_repo = secrets.token_hex()
        self.registration_token_org = secrets.token_hex()
        self.remove_token_repo = secrets.token_hex()
        self.remove_token_org = secrets.token_hex()

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

    def list_runner_applications_for_org(self, org: str):
        return self._list_runner_applications()

    def create_registration_token_for_repo(self, owner: str, repo: str):
        return RegistrationToken(
            {"token": self.registration_token_repo, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_registration_token_for_org(self, org: str):
        return RegistrationToken(
            {"token": self.registration_token_org, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_remove_token_for_repo(self, owner: str, repo: str):
        return RemoveToken(
            {"token": self.remove_token_repo, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_remove_token_for_org(self, org: str):
        return RemoveToken(
            {"token": self.remove_token_org, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def list_self_hosted_runners_for_repo(self, owner: str, repo: str):
        return {"runners": []}

    def list_self_hosted_runners_for_org(self, org: str):
        return {"runners": []}

    def delete_self_hosted_runner_from_repo(self, owner: str, repo: str, runner_id: str):
        pass

    def delete_self_hosted_runner_from_org(self, org: str, runner_id: str):
        pass


class MockRepoPolicyComplianceClient:
    """Mock for RepoPolicyComplianceClient."""

    def __init__(self, session=None, url=None, charm_token=None):
        pass

    def get_one_time_token(self) -> str:
        return "MOCK_TOKEN_" + secrets.token_hex(8)
