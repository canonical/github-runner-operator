# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Delete leftover OpenStack resources from github-runner-manager integration tests.

This module is used by the suite under ``github-runner-manager/tests/integration/``.
That suite runs the github-runner-manager application against a real OpenStack
cloud (servers and SSH keypairs named with the suite's ``test-runner-{id}``
prefix from ``factories.TestConfig``).

When a previous CI job is force-cancelled, those OpenStack resources can be
left behind. The next time this suite starts, it calls
:func:`cleanup_stale_openstack_resources` so older leftovers are removed
before new ones are created.
"""

import logging
from datetime import datetime, timedelta, timezone

import openstack.exceptions
from openstack.connection import Connection

from .factories import is_manager_openstack_resource_name

logger = logging.getLogger(__name__)


def _delete_resource(connection: Connection, label: str, name: str, delete_fn):
    """Delete a resource and log success or expected failure."""
    try:
        delete_fn()
        logger.info("Orphan cleanup deleted %s %s", label, name)
    except (openstack.exceptions.ResourceNotFound, openstack.exceptions.ConflictException):
        logger.warning("Orphan cleanup failed deleting %s %s", label, name, exc_info=True)


def _cleanup_servers(connection: Connection, now: datetime, min_age: timedelta):
    """Delete stale servers matching manager naming."""
    for server in connection.list_servers(bare=True) or []:
        name = getattr(server, "name", None)
        if not is_manager_openstack_resource_name(name):
            continue
        if not _is_stale(
            getattr(server, "created_at", None) or getattr(server, "created", None),
            min_age,
            now,
        ):
            continue
        _delete_resource(
            connection,
            "server",
            name or server.id,
            lambda s=server: connection.delete_server(s.id, wait=True),
        )


def _cleanup_keypairs(connection: Connection, now: datetime, min_age: timedelta):
    """Delete stale keypairs matching manager naming."""
    for keypair in connection.list_keypairs() or []:
        name = getattr(keypair, "name", None)
        if not is_manager_openstack_resource_name(name):
            continue
        if not _is_stale(getattr(keypair, "created_at", None), min_age, now):
            continue
        _delete_resource(
            connection,
            "keypair",
            name or "",
            lambda n=name: connection.delete_keypair(n),
        )


def cleanup_stale_openstack_resources(
    connection: Connection,
    min_age: timedelta = timedelta(hours=6),
) -> None:
    """Delete leftover OpenStack resources from previous suite runs.

    Args:
        connection: Authenticated OpenStack connection.
        min_age: Age threshold; resources newer than this are left alone.
    """
    now = datetime.now(tz=timezone.utc)
    logger.info("OpenStack orphan cleanup starting (min_age=%sh)", min_age.total_seconds() / 3600.0)
    _cleanup_servers(connection, now, min_age)
    _cleanup_keypairs(connection, now, min_age)
    logger.info("OpenStack orphan cleanup finished")


def _is_stale(created_at: object, min_age: timedelta, now: datetime) -> bool:
    """Return True if the resource is older than ``min_age``."""
    created = _parse_created_at(created_at)
    if created is None:
        return False
    return now - created >= min_age


def _parse_created_at(value: object) -> datetime | None:
    """Parse a created_at value into a UTC datetime, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
