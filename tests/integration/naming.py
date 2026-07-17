# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared naming for charm integration tests and OpenStack orphan cleanup.

Producers (fixtures) and consumers (orphan cleanup) both import from here so
resource name formats cannot drift.
"""

import random
import string

# Suffixes for app names are 8 characters: 1 lowercase letter + 7 alnum
# (see random_app_name_suffix historical shape).
TEST_ID_LENGTH = 8
TEST_ID_ALPHABET = string.ascii_lowercase + string.digits

# Longest-first matters for matching: "test-runner-" before "test-".
OPENSTACK_RESOURCE_PREFIXES: tuple[str, ...] = (
    "github-runner-image-builder-",  # image builder charm app in charm IT
    "test-runner-",  # github-runner-manager TestConfig.vm_prefix (shared tenant)
    "test-",  # github-runner charm app_name
)


def generate_app_suffix() -> str:
    """Return a fresh 8-char application name suffix for a suite run."""
    return random.choice(string.ascii_lowercase) + "".join(
        random.choices(TEST_ID_ALPHABET, k=TEST_ID_LENGTH - 1)
    )


def app_name_from_suffix(suffix: str) -> str:
    """github-runner application name for a given suffix."""
    return f"test-{suffix}"


def image_builder_app_name_from_suffix(suffix: str) -> str:
    """github-runner-image-builder application name for a given suffix."""
    return f"github-runner-image-builder-{suffix}"


def is_ci_openstack_resource_name(name: str | None) -> bool:
    """True if *name* matches a known CI/OpenStack resource prefix + test id.

    A resource is considered CI-created when it starts with one of
    :data:`OPENSTACK_RESOURCE_PREFIXES` followed by an 8-char test id, optionally
    with further ``-...`` segments (InstanceID-style suffixes).
    """
    if not name:
        return False
    for prefix in OPENSTACK_RESOURCE_PREFIXES:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        if not rest:
            continue
        test_id = rest.split("-", 1)[0]
        if len(test_id) == TEST_ID_LENGTH and all(c in TEST_ID_ALPHABET for c in test_id):
            return True
    return False
