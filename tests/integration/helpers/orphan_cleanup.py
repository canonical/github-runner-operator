# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Delete leftover OpenStack resources from github-runner charm integration tests.

This module is used by the suite under ``tests/integration/`` (the Juju charm
suite). That suite deploys the github-runner charm (and optionally related
helpers) and creates OpenStack servers, images, and keypairs whose names
follow the shared prefixes in :mod:`tests.integration.naming`
(for example ``test-{id}…``, ``test-runner-{id}…``,
``github-runner-image-builder-{id}…``).

When a previous CI job is force-cancelled, those OpenStack resources can be
left behind. The next time this suite starts, it calls
:func:`cleanup_stale_openstack_resources` so older leftovers are removed
before new ones are created.
"""

import logging
from datetime import datetime, timedelta, timezone

import openstack.exceptions
from openstack.connection import Connection

from tests.integration.naming import is_ci_openstack_resource_name

logger = logging.getLogger(__name__)


def cleanup_stale_openstack_resources(
    connection: Connection,
    min_age: timedelta = timedelta(hours=6),
) -> None:
    """Delete leftover OpenStack resources from previous suite runs older than ``min_age``."""
    now = datetime.now(tz=timezone.utc)
    logger.info(
        "OpenStack orphan cleanup starting (min_age=%sh)",
        min_age.total_seconds() / 3600.0,
    )

    for server in connection.list_servers(bare=True) or []:
        name = getattr(server, "name", None)
        if not is_ci_openstack_resource_name(name):
            continue
        if not _is_stale(
            getattr(server, "created_at", None) or getattr(server, "created", None),
            min_age,
            now,
        ):
            continue
        try:
            connection.delete_server(server.id, wait=True)
            logger.info("Orphan cleanup deleted server %s", name or server.id)
        except (openstack.exceptions.ResourceNotFound, openstack.exceptions.ConflictException):
            logger.warning(
                "Orphan cleanup failed deleting server %s", name or server.id, exc_info=True
            )

    for image in connection.list_images() or []:
        name = getattr(image, "name", None)
        visibility = str(getattr(image, "visibility", "") or "").lower()
        if visibility in {"public", "community"}:
            continue
        if not is_ci_openstack_resource_name(name):
            continue
        if not _is_stale(getattr(image, "created_at", None), min_age, now):
            continue
        try:
            connection.delete_image(image.id)
            logger.info("Orphan cleanup deleted image %s", name or image.id)
        except (openstack.exceptions.ResourceNotFound, openstack.exceptions.ConflictException):
            logger.warning(
                "Orphan cleanup failed deleting image %s", name or image.id, exc_info=True
            )

    for keypair in connection.list_keypairs() or []:
        name = getattr(keypair, "name", None)
        if not is_ci_openstack_resource_name(name):
            continue
        if not _is_stale(getattr(keypair, "created_at", None), min_age, now):
            continue
        try:
            connection.delete_keypair(name)
            logger.info("Orphan cleanup deleted keypair %s", name)
        except (openstack.exceptions.ResourceNotFound, openstack.exceptions.ConflictException):
            logger.warning(
                "Orphan cleanup failed deleting keypair %s", name, exc_info=True
            )

    logger.info("OpenStack orphan cleanup finished")


def _is_stale(created_at: object, min_age: timedelta, now: datetime) -> bool:
    """Return True if the resource is older than ``min_age``."""
    created = _parse_created_at(created_at)
    if created is None:
        return False
    return now - created >= min_age


def _parse_created_at(value: object) -> datetime | None:
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
