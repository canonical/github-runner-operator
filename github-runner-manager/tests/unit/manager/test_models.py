#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the manager models."""

import pytest

from github_runner_manager.manager.models import InstanceID, InstanceIDInvalidError


def test_new_instance_id():
    """
    arrange: Having an Application prefix.
    act: Create a new InstanceId.
    assert: The new instance fields are correct: same prefix, name starts with prefix,
       and contains n- prefix in the name.
    """
    prefix = "theprefix"

    instance_id = InstanceID.build("theprefix")

    assert instance_id.name == str(instance_id)
    assert instance_id.prefix == prefix
    assert instance_id.name.startswith(prefix)
    assert "-n-" not in instance_id.name


def test_build_instance_id_from_name():
    """
    arrange: Create a new InstanceID.
    act: With the name of the previous instance ID and the prefix, create a new one.
    assert: Both instances should be equal.
    """
    prefix = "theprefix"
    instance_id = InstanceID.build(prefix)

    name = instance_id.name
    new_instance_id = InstanceID.build_from_name(prefix, name)

    assert new_instance_id == instance_id
    assert new_instance_id.name == instance_id.name
    assert new_instance_id.suffix == instance_id.suffix


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


def test_backward_compatible_names_without_type_prefix():
    """
    arrange: A prefix and a name without r-/n- type prefix (old format).
    act: Create the instance ID from the prefix and name.
    assert: Suffix is parsed correctly. New name includes n- prefix.
    """
    prefix = "unit-0"
    name = "unit-0-96950f351751"

    instance_id = InstanceID.build_from_name(prefix, name)

    assert instance_id.prefix == prefix
    assert instance_id.suffix == "96950f351751"
    assert instance_id.name == "unit-0-96950f351751"


def test_backward_compatible_names_with_reactive_prefix():
    """
    arrange: A prefix and a name with legacy r- (reactive) prefix.
    act: Create the instance ID from the prefix and name.
    assert: The r- prefix is preserved in .name so the VM can be looked up.
    """
    prefix = "unit-0"
    name = "unit-0-r-96950f351751"

    instance_id = InstanceID.build_from_name(prefix, name)

    assert instance_id.prefix == prefix
    assert instance_id.suffix == "96950f351751"
    assert instance_id.name == name


def test_backward_compatible_names_with_non_reactive_prefix():
    """
    arrange: A prefix and a name with legacy n- (non-reactive) prefix.
    act: Create the instance ID from the prefix and name.
    assert: The n- prefix is preserved in .name so the VM can be looked up.
    """
    prefix = "unit-0"
    name = "unit-0-n-96950f351751"

    instance_id = InstanceID.build_from_name(prefix, name)

    assert instance_id.prefix == prefix
    assert instance_id.suffix == "96950f351751"
    assert instance_id.name == name
