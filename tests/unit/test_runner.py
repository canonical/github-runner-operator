#!/usr/bin/env python3
import unittest
from unittest import mock

import pytest
from pylxd.exceptions import LXDAPIException

from runner import RunnerError, RunnerInfo, RunnerManager, VMResources


class TestRunner(unittest.TestCase):
    def setUp(self):
        mocker_pylxd = mock.patch("runner.pylxd")
        mock_pylxd = mocker_pylxd.start()
        self.lxd = mock_pylxd.Client.return_value = mock.MagicMock()
        self.addCleanup(mocker_pylxd.stop)

    @mock.patch("runner.choices", return_value="1234")
    def test_create_instance(self, _):
        """Test function for creating instances."""
        # no runner profile exists, creating container
        self.lxd.profiles.exists.return_value = False

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._create_instance(virt="container")
        self.lxd.profiles.create.assert_called_once_with(
            "runner", {"security.nesting": "true", "security.privileged": "true"}, {}
        )
        self.lxd.instances.create.assert_called_once_with(config=mock.ANY, wait=True)
        self.lxd.reset_mock()

        # runner profile exists, creating container
        self.lxd.profiles.exists.return_value = True

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._create_instance(virt="container")
        self.lxd.profiles.create.assert_not_called()
        self.lxd.instances.create.assert_called_once_with(config=mock.ANY, wait=True)
        self.lxd.reset_mock()

        # runner profile exists, creating virtual-machine without vm-resources specify
        self.lxd.profiles.exists.return_value = True

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._create_instance(virt="virtual-machine")
        self.lxd.profiles.create.assert_not_called()
        self.lxd.instances.create.assert_called_once_with(config=mock.ANY, wait=True)
        self.lxd.reset_mock()

        # runner profile exists, creating virtual-machine with vm-resources specify
        self.lxd.profiles.exists.return_value = True

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._create_instance(virt="virtual-machine", vm_resources=VMResources(4, "7GiB", "10GiB"))
        self.lxd.profiles.create.assert_called_once_with(
            "test-1234",
            {"limits.cpu": "4", "limits.memory": "7GiB"},
            {"root": {"path": "/", "pool": "default", "type": "disk", "size": "10GiB"}},
        )
        self.lxd.instances.create.assert_called_once_with(config=mock.ANY, wait=True)
        self.lxd.reset_mock()

    def test_create_vm_profile(self):
        """Test creation of VM profile."""
        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)

        # without any error
        rm._create_vm_profile("test", vm_resources=VMResources(2, "4GiB", "20GiB"))
        self.lxd.profiles.create.assert_called_once_with(
            "test",
            {"limits.cpu": "2", "limits.memory": "4GiB"},
            {"root": {"path": "/", "pool": "default", "type": "disk", "size": "20GiB"}},
        )
        self.lxd.reset_mock()

        # vm-resources not valid object
        with pytest.raises(RunnerError):
            rm._create_vm_profile("test", vm_resources=[2, "4GiB", "20GiB"])

        self.lxd.profiles.create.assert_not_called()

        # lxd profile creation failed
        self.lxd.profiles.create.side_effect = LXDAPIException(response=mock.MagicMock())
        with pytest.raises(RunnerError):
            rm._create_vm_profile("test", vm_resources=VMResources(2, "4GiB", "10GiB"))

    def test_remove_runner(self):
        """Test remove runner function.

        Note: This function is not completed, it tests only profile removal.
        """
        runner = RunnerInfo("test-1234", None, None)
        profile = self.lxd.profiles.get.return_value = mock.MagicMock()

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._remove_runner(runner)
        self.lxd.profiles.get.assert_called_once_with(runner.name)
        profile.delete.assert_called_once()

    def test_clean_unused_profiles(self):
        """Test function to clean all unused LXD profiles."""
        used_profile = mock.MagicMock()
        used_profile.name = "test-1234"
        used_profile.used_by = ["test-1234"]
        unused_profile = mock.MagicMock()
        unused_profile.name = "test-1235"
        unused_profile.used_by = []
        self.lxd.profiles.all.return_value = [used_profile, unused_profile]

        rm = RunnerManager("mockorg/repo", "mocktoken", "test", 5)
        rm._clean_unused_profiles()
        used_profile.delete.assert_not_called()
        unused_profile.delete.assert_called_once()
