#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the manager models."""

import pytest

from github_runner_manager.manager.models import InstanceID, InstanceIDInvalidError


def test_new_instance_id():
    """
    arrange: Having an Application prefix.
    act: Create a new InstanceId.
    assert: The new instance fields are correct, that is, same prefix and the
       name starts with the prefix and reactive is False.
    """
    prefix = "theprefix"

    instance_id = InstanceID.build("theprefix")

    assert instance_id.name == str(instance_id)
    assert instance_id.prefix == prefix
    assert not instance_id.reactive
    assert instance_id.name.startswith(prefix)


@pytest.mark.parametrize(
    "reactive",
    [
        pytest.param(True, id="reactive job name"),
        pytest.param(False, id="non reactive job name"),
    ],
)
def test_build_instance_id_from_name(reactive):
    """
    arrange: Create a new InstanceID.
    act: With the name of the previous instance ID and the prefix, create a new one.
    assert: Both instances should be equal.
    """
    prefix = "theprefix"
    instance_id = InstanceID.build(prefix, reactive)

    name = instance_id.name
    new_instance_id = InstanceID.build_from_name(prefix, name)

    assert new_instance_id == instance_id
    assert new_instance_id.name == instance_id.name
    assert new_instance_id.suffix == instance_id.suffix
    assert new_instance_id.reactive == reactive


def test_build_instance_id_from_name_fails_with_wrong_prefix():
    """
    arrange: Create an instance ID with a prefix..
    act: Build from the previous instance ID name and another prefix.
    assert: A ValueError exception should be raised.
    """
    prefix = "theprefix"
    instance_id = InstanceID.build(prefix)

    name = "wrong" + instance_id.name

    with pytest.raises(ValueError):
        _ = InstanceID.build_from_name(prefix, name)


def test_build_instance_id_fails_when_very_long_name():
    """
    arrange: -.
    act: Create a new InstanceID with a very long prefix.
    assert: A InstanceIDInvalidError exception should be raised.
    """
    prefix = "github-runner-operator-for-runners-using-openstack-amd64-with-flavor-with60-cores"
    with pytest.raises(InstanceIDInvalidError):
        _ = InstanceID.build(prefix)


def test_backward_compatible_names():
    """
    arrange: A prefix and a unit name without reactive information.
    act: Create the instance ID from the prefix and name.
    assert: New name from the instance is the same as the original name. Also prefix and suffix.
    """
    prefix = "unit-0"
    name = "unit-0-96950f351751"

    instance_id = InstanceID.build_from_name(prefix, name)

    assert instance_id.prefix == prefix
    assert instance_id.suffix == "96950f351751"
    assert instance_id.name == name
