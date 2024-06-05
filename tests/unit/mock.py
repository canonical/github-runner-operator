# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Mock for testing."""

from __future__ import annotations

import hashlib
import io
import logging
import secrets
from pathlib import Path
from typing import IO, Optional, Sequence, Union

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
        """Fake init implementation for LxdClient."""
        self.instances = MockLxdInstanceManager()
        self.profiles = MockLxdProfileManager()
        self.networks = MockLxdNetworkManager()
        self.storage_pools = MockLxdStoragePoolManager()
        self.images = MockLxdImageManager()


class MockLxdInstanceManager:
    """Mock the behavior of the LXD Instances."""

    def __init__(self):
        """Fake init implementation for LxdInstanceManager."""
        self.instances = {}

    def create(self, config: LxdInstanceConfig, wait: bool = False) -> MockLxdInstance:
        """Create an instance with given config.

        Args:
            config: The instance configuration to create the instance with.
            wait: Placeholder for wait argument.

        Returns:
            Mock instance that was created.
        """
        self.instances[config["name"]] = MockLxdInstance(config["name"])
        return self.instances[config["name"]]

    def get(self, name: str):
        """Get an instance with given name.

        Args:
            name: The name of the instance to get.

        Returns:
            Instance with given name.
        """
        return self.instances[name]

    def all(self):
        """Return all instances that have not been deleted.

        Returns:
            All Lxd fake instances that have not been deleted.
        """
        return [i for i in self.instances.values() if not i.deleted]


class MockLxdProfileManager:
    """Mock the behavior of the LXD Profiles."""

    def __init__(self):
        """Initialization method for LxdProfileManager fake."""
        self.profiles = set()

    def create(self, name: str, config: dict[str, str], devices: dict[str, str]):
        """Fake implementation of create method of LxdProfile manager.

        Args:
            name: The name of LXD profile.
            config: The config of LXD profile to create.
            devices: The devices mapping of LXD profile to create with.
        """
        self.profiles.add(name)

    def exists(self, name: str) -> bool:
        """Fake implementation of exists method of LxdProfile manager.

        Args:
            name: The name of LXD profile.

        Returns:
            Whether given LXD profile exists.
        """
        return name in self.profiles


class MockLxdNetworkManager:
    """Mock the behavior of the LXD networks."""

    def __init__(self):
        """Placeholder for initialization method for LxdInstance stub."""
        pass

    def get(self, name: str) -> LxdNetwork:
        """Stub method get for LxdNetworkManager.

        Args:
            name: the name of the LxdNetwork to get.

        Returns:
            LxdNetwork stub.
        """
        return LxdNetwork(
            "lxdbr0", "", "bridge", {"ipv4.address": "10.1.1.1/24"}, True, ("default")
        )


class MockLxdInstance:
    """Mock the behavior of an LXD Instance."""

    def __init__(self, name: str):
        """Fake implementation of initialization method for LxdInstance fake.

        Args:
            name: The mock instance name to create.
        """
        self.name = name
        self.status = "Stopped"
        self.deleted = False

        self.files = MockLxdInstanceFileManager()

    def start(self, wait: bool = True, timeout: int = 60):
        """Fake implementation of start method for LxdInstance fake.

        Args:
            wait: Placeholder for wait argument.
            timeout: Placeholder for timeout argument.
        """
        self.status = "Running"

    def stop(self, wait: bool = True, timeout: int = 60):
        """Fake implementation of stop method for LxdInstance fake.

        Args:
            wait: Placeholder for wait argument.
            timeout: Placeholder for timeout argument.
        """
        self.status = "Stopped"
        # Ephemeral virtual machine should be deleted on stop.
        self.deleted = True

    def delete(self, wait: bool = True):
        """Fake implementation of delete method for LxdInstance fake.

        Args:
            wait: Placeholder for wait argument.
        """
        self.deleted = True

    def execute(
        self, cmd: Sequence[str], cwd: Optional[str] = None, hide_cmd: bool = False
    ) -> tuple[int, IO, IO]:
        """Implementation for execute for LxdInstance fake.

        Args:
            cmd: Placeholder for command to execute.
            cwd: Placeholder for working directory to execute command.
            hide_cmd: Placeholder for to hide command that is being executed.

        Returns:
            Empty tuples values that represent a successful command execution.
        """
        return 0, io.BytesIO(b""), io.BytesIO(b"")


class MockLxdInstanceFileManager:
    """Mock the behavior of an LXD Instance's files."""

    def __init__(self):
        """Initializer for fake instance of LxdInstanceFileManager."""
        self.files = {}

    def mk_dir(self, path):
        """Placeholder for mk_dir implementation of LxdInstanceFileManager.

        Args:
            path: The path to create.
        """
        pass

    def push_file(self, source: str, destination: str, mode: Optional[str] = None):
        """Fake push_file implementation of LxdInstanceFileManager.

        Args:
            source: Placeholder argument for source file path copy from.
            destination: File path to write to.
            mode: Placeholder for file write mode.
        """
        self.files[destination] = "mock_content"

    def write_file(self, filepath: str, data: Union[bytes, str], mode: Optional[str] = None):
        """Fake write_file implementation of LxdInstanceFileManager.

        Args:
            filepath: The file path to read.
            data: File contents to write
            mode: Placeholder for file write mode.
        """
        self.files[filepath] = data

    def read_file(self, filepath: str):
        """Fake read_file implementation of LxdInstanceFileManager.

        Args:
            filepath: The file path to read.

        Returns:
            Contents of file.
        """
        return self.files.get(str(filepath), None)


class MockLxdStoragePoolManager:
    """Mock the behavior of LXD storage pools."""

    def __init__(self):
        """Initialize fake storage pools."""
        self.pools = {}

    def all(self):
        """Get all non-deleted fake lxd storage pools.

        Returns:
            List of all non deleted fake LXD storages.
        """
        return [pool for pool in self.pools.values() if not pool.deleted]

    def get(self, name):
        """Get a fake storage pool of given name.

        Args:
            name: Name of the storage pool to get.

        Returns:
            Fake storage pool of given name.
        """
        return self.pools[name]

    def exists(self, name):
        """Check if given storage exists in the fake LxdStoragePool.

        Args:
            name: Fake storage pool name to check for existence.

        Returns:
            If storage pool of given name exists.
        """
        if name in self.pools:
            return not self.pools[name].deleted
        else:
            return False

    def create(self, config):
        """Fake LxdStoragePoolManager create function.

        Args:
            config: The LXD storage pool config.

        Returns:
            Created LXDStoragePool fake.
        """
        self.pools[config["name"]] = MockLxdStoragePool()
        return self.pools[config["name"]]


class MockLxdStoragePool:
    """Mock the behavior of an LXD storage pool."""

    def __init__(self):
        """LXD storage pool fake initialization method."""
        self.deleted = False

    def save(self):
        """LXD storage pool fake save method placeholder."""
        pass

    def delete(self):
        """LXD storage pool fake delete method."""
        self.deleted = True


class MockLxdImageManager:
    """Mock the behavior of LXD images."""

    def __init__(self, images: set[str] | None = None):
        """Fake init implementation for LxdImageManager.

        Args:
            images: Set of images to initialize.
        """
        self.images: set[str] = images or set()

    def create(self, name: str, _: Path) -> None:
        """Import an LXD image into the fake set.

        Args:
            name: Alias for the image.
            _: Path of the LXD image file.
        """
        self.images.add(name)

    def exists(self, name: str) -> bool:
        """Check if an image with the given name exists.

        Args:
            name: image name.

        Returns:
            Whether the image exists.
        """
        return name in self.images


class MockErrorResponse:
    """Mock of an error response for request library."""

    def __init__(self):
        """Successful error response initialization method."""
        self.status_code = 200

    def json(self):
        """A stub method that always returns error response.

        Returns:
            Test error response.
        """
        return {"metadata": {"err": "test error"}}


def mock_lxd_error_func(*args, **kwargs):
    """A stub function that always raises LxdError.

    Args:
        args: Placeholder for positional arguments.
        kwargs: Placeholder for key word arguments.

    Raises:
        LxdError: always.
    """
    raise LxdError(MockErrorResponse())


def mock_runner_error_func(*args, **kwargs):
    """A stub function that always raises RunnerError.

    Args:
        args: Placeholder for positional arguments.
        kwargs: Placeholder for key word arguments.

    Raises:
        RunnerError: always.
    """
    raise RunnerError("test error")


class MockGhapiClient:
    """Mock for Ghapi client."""

    def __init__(self, token: str):
        """Initialization method for GhapiClient fake.

        Args:
            token: The client token value.
        """
        self.token = token
        self.actions = MockGhapiActions()

    def last_page(self) -> int:
        """Last page number stub.

        Returns:
            Always zero.
        """
        return 0


class MockGhapiActions:
    """Mock for actions in Ghapi client."""

    def __init__(self):
        """A placeholder method for test stub/fakes initialization."""
        hash = hashlib.sha256()
        hash.update(TEST_BINARY)
        self.test_hash = hash.hexdigest()
        self.registration_token_repo = secrets.token_hex()
        self.registration_token_org = secrets.token_hex()
        self.remove_token_repo = secrets.token_hex()
        self.remove_token_org = secrets.token_hex()

    def _list_runner_applications(self):
        """A placeholder method for test fake.

        Returns:
            A fake runner applications list.
        """
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
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.

        Returns:
            A fake runner applications list.
        """
        return self._list_runner_applications()

    def list_runner_applications_for_org(self, org: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.

        Returns:
            A fake runner applications list.
        """
        return self._list_runner_applications()

    def create_registration_token_for_repo(self, owner: str, repo: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.

        Returns:
            Registration token stub.
        """
        return RegistrationToken(
            {"token": self.registration_token_repo, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_registration_token_for_org(self, org: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.

        Returns:
            Registration token stub.
        """
        return RegistrationToken(
            {"token": self.registration_token_org, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_remove_token_for_repo(self, owner: str, repo: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.

        Returns:
            Remove token stub.
        """
        return RemoveToken(
            {"token": self.remove_token_repo, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def create_remove_token_for_org(self, org: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.

        Returns:
            Remove token stub.
        """
        return RemoveToken(
            {"token": self.remove_token_org, "expires_at": "2020-01-22T12:13:35.123-08:00"}
        )

    def list_self_hosted_runners_for_repo(
        self, owner: str, repo: str, per_page: int, page: int = 0
    ):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.
            per_page: Placeholder for responses per page.
            page: Placeholder for response page number.

        Returns:
            Empty runners stub.
        """
        return {"runners": []}

    def list_self_hosted_runners_for_org(self, org: str, per_page: int, page: int = 0):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for repository owner.
            per_page: Placeholder for responses per page.
            page: Placeholder for response page number.

        Returns:
            Empty runners stub.
        """
        return {"runners": []}

    def delete_self_hosted_runner_from_repo(self, owner: str, repo: str, runner_id: str):
        """A placeholder method for test stub.

        Args:
            owner: Placeholder for repository owner.
            repo: Placeholder for repository name.
            runner_id: Placeholder for runenr_id.
        """
        pass

    def delete_self_hosted_runner_from_org(self, org: str, runner_id: str):
        """A placeholder method for test stub.

        Args:
            org: Placeholder for organisation.
            runner_id: Placeholder for runner id.
        """
        pass


class MockRepoPolicyComplianceClient:
    """Mock for RepoPolicyComplianceClient."""

    def __init__(self, session=None, url=None, charm_token=None):
        """Placeholder method for initialization.

        Args:
            session: Placeholder for requests session.
            url: Placeholder for repo policy compliance url.
            charm_token: Placeholder for charm token.
        """
        pass

    def get_one_time_token(self) -> str:
        """Generate a test token value.

        Returns:
            A test token value.
        """
        return "MOCK_TOKEN_" + secrets.token_hex(8)
