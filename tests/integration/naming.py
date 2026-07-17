# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared application/OpenStack resource naming for charm integration tests.

Who uses this module
--------------------
- Producers: fixtures in ``tests/integration/conftest.py`` that choose Juju app
  names and related OpenStack resource names for a suite run.
- Consumers: ``tests/integration/helpers/orphan_cleanup.py``, which deletes
  leftover OpenStack resources from force-cancelled previous runs.

Keeping both sides on the same helpers means renaming a resource format only
requires changing this file once.
"""

import random
import string

# Application name suffixes are 8 characters: 1 lowercase letter + 7 alnum.
# Matches the historical ``random_app_name_suffix`` shape used by the charm suite.
TEST_ID_LENGTH = 8
TEST_ID_ALPHABET = string.ascii_lowercase + string.digits

# OpenStack / app name prefixes produced by this repository's integration tests.
# Longer prefixes are listed first so readers see the more specific form before
# the shorter ``test-`` prefix (``test-runner-`` vs ``test-``).
OPENSTACK_RESOURCE_PREFIXES: tuple[str, ...] = (
    "github-runner-image-builder-",  # image-builder charm app name in the charm suite
    "test-runner-",  # github-runner-manager VM/keypair prefix (shared CI tenant)
    "test-",  # github-runner charm application name
)


def generate_app_suffix() -> str:
    """Return a unique application name suffix for one suite run."""
    return random.choice(string.ascii_lowercase) + "".join(
        random.choices(TEST_ID_ALPHABET, k=TEST_ID_LENGTH - 1)
    )


def app_name_from_suffix(suffix: str) -> str:
    """Return the github-runner application name for *suffix*."""
    return f"test-{suffix}"


def image_builder_app_name_from_suffix(suffix: str) -> str:
    """Return the github-runner-image-builder application name for *suffix*."""
    return f"github-runner-image-builder-{suffix}"


def is_ci_openstack_resource_name(name: str | None) -> bool:
    """Return True if *name* belongs to this repository's CI OpenStack resources."""
    if not name:
        return False
    for prefix in OPENSTACK_RESOURCE_PREFIXES:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        if not rest:
            continue
        test_id = rest.split("-", 1)[0]
        if len(test_id) != TEST_ID_LENGTH:
            continue
        if not all(c in TEST_ID_ALPHABET for c in test_id):
            continue
        # Charm app suffixes always start with a letter; manager test ids may
        # start with a digit.
        if prefix != "test-runner-" and not test_id[0].isalpha():
            continue
        return True
    return False
