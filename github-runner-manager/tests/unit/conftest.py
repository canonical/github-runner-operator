#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test setups and configurations."""

import getpass
import grp
import os
from unittest.mock import MagicMock

import pytest

from src.github_runner_manager.configuration import UserInfo


@pytest.fixture(name="user_info", scope="module")
def user_info_fixture():
    return UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()).gr_name)


@pytest.fixture(name="patch_multiprocess_pool_imap_unordered", scope="function")
def patch_multiprocess_pool_imap_unordered_fixture(monkeypatch: pytest.MonkeyPatch):
    """Patch multiprocessing pool call to call the function directly."""

    def call_direct(func_var, params):
        """Function to replace imap_unordered with, by calling functions directly.

        Args:
            func_var: The function to call in imap_unordered call.
            params: The iterable parameters for target function.

        Yields:
            The function return value.
        """
        for param in params:
            yield func_var(param)

    pool_mock = MagicMock()
    pool_mock.return_value = pool_mock
    pool_mock.__enter__ = pool_mock
    pool_mock.imap_unordered = call_direct
    monkeypatch.setattr("multiprocessing.pool.Pool", pool_mock)
