# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Delete stale OpenStack resources left by interrupted CI integration runs.

Called at the start of integration tests so force-cancelled previous jobs still
get cleaned up the next time a suite runs against the tenant.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from collections.abc import Callable, Iterable

from openstack.connection import Connection

logger = logging.getLogger(__name__)

# Permanent SGs used by runtime code — never touch.
_PROTECTED_NAMES = frozenset(
    {
        "github-runner-v1",
        "github-runner-image-builder-v1",
        "default",
    }
)

# CI leftovers from this repository's charm + manager integration tests.
_NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^test-runner-[a-z0-9]{6,12}($|-)",  # manager TestConfig.vm_prefix
        r"^test-[a-z0-9]{6,12}($|-)",  # charm app_name
        r"^github-runner-image-builder-[a-z0-9]{6,12}($|-)",  # image-builder deploy in charm IT
    )
)

_SG_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^test-runner-[a-z0-9]{6,12}-",
        r"^test-[a-z0-9]{6,12}-",
    )
)


def cleanup_stale_openstack_resources(
    connection: Connection,
    min_age: timedelta = timedelta(hours=6),
) -> None:
    """Remove CI-named OpenStack resources older than ``min_age``.

    Order: servers (may hold SG/keypair refs) → images → keypairs → security groups.
    """
    now = datetime.now(tz=timezone.utc)
    logger.info(
        "OpenStack orphan cleanup starting (min_age=%sh)",
        min_age.total_seconds() / 3600.0,
    )

    for server in connection.list_servers(bare=True) or []:
        name = getattr(server, "name", None)
        if not _matches(name, _NAME_PATTERNS):
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
            lambda s=server: connection.delete_server(s.id, wait=False),
        )

    for image in connection.list_images() or []:
        name = getattr(image, "name", None)
        visibility = str(getattr(image, "visibility", "") or "").lower()
        if visibility in {"public", "community"}:
            continue
        if not _matches(name, _NAME_PATTERNS):
            continue
        if not _is_stale(getattr(image, "created_at", None), min_age, now):
            continue
        _safe_delete(
            "image",
            name or image.id,
            lambda im=image: connection.delete_image(im.id, wait=False),
        )

    for keypair in connection.list_keypairs() or []:
        name = getattr(keypair, "name", None)
        if not _matches(name, _NAME_PATTERNS):
            continue
        if not _is_stale(getattr(keypair, "created_at", None), min_age, now):
            continue
        _safe_delete(
            "keypair",
            name or "",
            lambda n=name: connection.delete_keypair(n),
        )

    for sg in connection.list_security_groups() or []:
        name = getattr(sg, "name", None)
        if name in _PROTECTED_NAMES:
            continue
        if not (_matches(name, _SG_PATTERNS) or _matches(name, _NAME_PATTERNS)):
            continue
        if not _is_stale(getattr(sg, "created_at", None), min_age, now):
            continue
        _safe_delete(
            "security_group",
            name or sg.id,
            lambda g=sg: connection.delete_security_group(g.id),
        )

    logger.info("OpenStack orphan cleanup finished")


def _safe_delete(label: str, name: str, delete_fn: Callable[[], object]) -> None:
    try:
        delete_fn()
        logger.info("Orphan cleanup deleted %s %s", label, name)
    except Exception as exc:  # noqa: BLE001 - best-effort, already-gone is fine
        logger.warning("Orphan cleanup failed deleting %s %s: %s", label, name, exc)


def _is_stale(created_at: object, min_age: timedelta, now: datetime) -> bool:
    """True if resource should be deleted.

    Missing created_at: treat as stale (keypair API often lacks timestamps).
    """
    created = _parse_created_at(created_at)
    if created is None:
        return True
    return now - created >= min_age


def _matches(name: str | None, patterns: Iterable[re.Pattern[str]]) -> bool:
    if not name or name in _PROTECTED_NAMES:
        return False
    return any(p.search(name) for p in patterns)


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
