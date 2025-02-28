#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit test for the manager models."""

import pytest

from github_runner_manager.manager.models import InstanceID


def test_new_instance_id():
    """
    arrange: TODO.
    act: TODO
    assert: TODO
    """
    prefix = "theprefix"
    instance_id = InstanceID.build("theprefix")

    assert instance_id.name == str(instance_id)
    assert instance_id.prefix == prefix
    assert not instance_id.reactive
    assert instance_id.name.startswith(prefix)
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
    arrange: TODO.
    act: TODO
    assert: TODO
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
    arrange: TODO.
    act: TODO
    assert: TODO
    """
    prefix = "theprefix"
    instance_id = InstanceID.build(prefix)

    name = "wrong" + instance_id.name

    with pytest.raises(ValueError):
        _ = InstanceID.build_from_name(prefix, name)
