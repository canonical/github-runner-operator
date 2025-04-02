#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test setups and configurations."""

import getpass
import grp
import os

import pytest

from src.github_runner_manager.configuration import UserInfo


@pytest.fixture(name="user_info", scope="module")
def user_info_fixture():
    return UserInfo(getpass.getuser(), str(grp.getgrgid(os.getgid())))
