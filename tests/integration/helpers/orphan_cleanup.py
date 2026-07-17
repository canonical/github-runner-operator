# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Delete stale OpenStack resources left by interrupted CI integration runs.

Called at the start of integration tests so force-cancelled previous jobs still
get cleaned up the next time a suite runs against the tenant.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from openstack.connection import Connection

from tests.integration.naming import is_ci_openstack_resource_name

logger = logging.getLogger(__name__)


def cleanup_stale_openstack_resources(
    connection: Connection,
    min_age: timedelta = timedelta(hours=6),
) -> None:
    """Remove CI-named OpenStack resources older than ``min_age``.

    Order: servers (hold keypairs/refs) → images → keypairs.
    Security groups are not touched: runtime uses a permanent docker-project
    group (``github-runner-v1``) that is get-or-create, never suite-scoped.
    """
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
        _safe_delete(
            "server",
            name or server.id,
            lambda s=server: connection.delete_server(s.id, wait=True),
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
        _safe_delete(
            "image",
            name or image.id,
            lambda im=image: connection.delete_image(im.id),
        )

    for keypair in connection.list_keypairs() or []:
        name = getattr(keypair, "name", None)
        if not is_ci_openstack_resource_name(name):
            continue
        if not _is_stale(getattr(keypair, "created_at", None), min_age, now):
            continue
        _safe_delete("keypair", name or "", lambda n=name: connection.delete_keypair(n))

    logger.info("OpenStack orphan cleanup finished")


def _safe_delete(label: str, name: str, delete_fn: Callable[[], object]) -> None:
    try:
        delete_fn()
        logger.info("Orphan cleanup deleted %s %s", label, name)
    except Exception as exc:  # noqa: BLE001 - best-effort, already-gone is fine
        logger.warning(
            "Orphan cleanup failed deleting %s %s: %s", label, name, exc, exc_info=True
        )


def _is_stale(created_at: object, min_age: timedelta, now: datetime) -> bool:
    """True if resource is dated and older than ``min_age``.

    Missing/unparseable created_at: skip. Unknown age must not delete concurrent
    or in-progress CI resources (e.g. keypairs without timestamps).
    """
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
