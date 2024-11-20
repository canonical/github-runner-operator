#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for testing the general types."""
import pytest

from github_runner_manager.types_ import ProxyConfig


def test_check_use_aproxy():
    """
    arrange: Create a dictionary of values representing a proxy configuration with use_aproxy set\
        to True but neither http nor https provided.
    act: Call the check_use_aproxy method with the provided values.
    assert: Verify that the method raises a ValueError with the expected message.
    """
    values = {"http": None, "https": None}
    use_aproxy = True

    with pytest.raises(ValueError) as exc_info:
        ProxyConfig.check_use_aproxy(use_aproxy, values)

    assert str(exc_info.value) == "aproxy requires http or https to be set"
