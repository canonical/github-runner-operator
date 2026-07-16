#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Delete old CI-created OpenStack resources in a single tenant/project.

Designed for the scheduled GitHub Actions workflow (and ad-hoc local runs).
Default mode is dry-run; pass --apply to delete.

Resources covered (name-pattern based):
  * servers (Nova instances / builder VMs / runner VMs)
  * keypairs
  * glance images (built test images / base seeds with CI prefixes)
  * security groups (test-only; shared permanent groups are never touched)

Authentication (any one of):
  * OS_* environment variables (OS_AUTH_URL, OS_PROJECT_NAME, ...)
  * openstacksdk clouds.yaml via --os-cloud / OS_CLOUD
  * explicit --clouds-file + --os-cloud

Examples:
  # List what would be deleted (older than 6h):
  ./cleanup_openstack_ci_resources.py --min-age-hours 6

  # Actually delete:
  ./cleanup_openstack_ci_resources.py --min-age-hours 6 --apply

  # Use a named cloud from clouds.yaml:
  OS_CLOUD=ci-tenant ./cleanup_openstack_ci_resources.py --apply --min-age-hours 12
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

try:
    import openstack
    from openstack.connection import Connection
except ImportError:  # pragma: no cover - runtime dependency check
    print(
        "error: openstacksdk is required. Install with:\n"
        "  pip install openstacksdk\n"
        "  # or: apt install python3-openstacksdk",
        file=sys.stderr,
    )
    sys.exit(2)

LOG = logging.getLogger("cleanup_openstack_ci")

# ---------------------------------------------------------------------------
# Name matchers
#
# Derived from integration fixtures / product naming in:
#   github-runner-operator  (charm + github-runner-manager)
#   github-runner-image-builder-operator  (charm + app)
#
# Permanent / shared names that production and refits reuse must stay excluded.
# ---------------------------------------------------------------------------

# Never delete these even if they match something else.
PROTECTED_EXACT_NAMES: frozenset[str] = frozenset(
    {
        # github-runner-manager shared SG (openstack_cloud._SECURITY_GROUP_NAME)
        "github-runner-v1",
        # image-builder shared SG (openstack_builder.SHARED_SECURITY_GROUP_NAME)
        "github-runner-image-builder-v1",
        # default OpenStack groups
        "default",
    }
)

# Server / keypair / image name patterns treated as CI leftovers.
# Each pattern is applied to the full resource name.
NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        # github-runner-manager integration: TestConfig.vm_prefix = test-runner-{8}
        r"^test-runner-[a-z0-9]{6,12}($|-)",
        # github-runner charm integration app: test-{8} (+ unit/VM suffix)
        r"^test-[a-z0-9]{6,12}($|-)",
        # image-builder operator charm app names
        r"^image-builder-operator-[0-9a-f]{6,16}($|-)",
        r"^image-builder-charmhub-[0-9a-f]{6,16}($|-)",
        # GRO deploys image-builder as github-runner-image-builder-{suffix}
        r"^github-runner-image-builder-[a-z0-9]{6,12}($|-)",
        # image-builder app integration fixtures
        r"^test-image-builder-",
        # keypair / builder naming: {prefix}-image-builder-...
        # 2-char test_id prefixes only accepted when the rest is image-builder-related
        r"^[a-z0-9]{2,16}-image-builder-(base-|ssh-key$|test$|[a-z0-9]+-[a-z0-9]+$)",
        r"^[a-z0-9]{2,16}-image-builder-[a-z0-9]+-[a-z0-9]+$",
    )
)

# Extra security-group patterns (not covered cleanly by server-name family).
SG_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^github-runner-image-builder-test-security-group-",
        r"^github-runner-image-builder-operator-test-security-group",
        # manager-test SGs named after vm_prefix if any
        r"^test-runner-[a-z0-9]{6,12}-",
        r"^test-[a-z0-9]{6,12}-",
    )
)


@dataclass
class ResourceHit:
    kind: str
    name: str
    resource_id: str
    created_at: datetime | None
    age: timedelta | None
    detail: str = ""


@dataclass
class Stats:
    considered: int = 0
    matched: int = 0
    too_young: int = 0
    protected: int = 0
    deleted: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)


def _parse_openstack_timestamp(value: Any) -> datetime | None:
    """Parse OpenStack created_at / updated_at into aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    # Common forms: 2026-07-16T12:34:56Z / 2026-07-16T12:34:56.123456
    text = text.replace("Z", "+00:00")
    # Some APIs omit timezone; treat as UTC.
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                dt = datetime.strptime(text.split("+")[0], fmt)
                break
            except ValueError:
                continue
        else:
            LOG.warning("unparseable timestamp %r", value)
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _name_matches(name: str | None, patterns: Iterable[re.Pattern[str]]) -> bool:
    if not name:
        return False
    if name in PROTECTED_EXACT_NAMES:
        return False
    return any(p.search(name) for p in patterns)


def _connect(args: argparse.Namespace) -> Connection:
    kwargs: dict[str, Any] = {}
    if args.clouds_file:
        kwargs["config_files"] = [args.clouds_file]
    if args.os_cloud:
        kwargs["cloud"] = args.os_cloud
    # openstack.connect() also reads OS_* env vars automatically.
    conn = openstack.connect(**kwargs)
    # Force auth early so failures are loud.
    conn.authorize()
    return conn


def _age_ok(created: datetime | None, min_age: timedelta, now: datetime) -> tuple[bool, timedelta | None]:
    """Return (eligible, age). Missing created_at: treat as eligible (stale leftover)."""
    if created is None:
        return True, None
    age = now - created
    return age >= min_age, age


def _scan_servers(conn: Connection, min_age: timedelta, now: datetime) -> list[ResourceHit]:
    hits: list[ResourceHit] = []
    for server in conn.list_servers(bare=True) or []:
        name = getattr(server, "name", None)
        if not _name_matches(name, NAME_PATTERNS):
            continue
        created = _parse_openstack_timestamp(getattr(server, "created_at", None) or getattr(server, "created", None))
        eligible, age = _age_ok(created, min_age, now)
        hits.append(
            ResourceHit(
                kind="server",
                name=name or "",
                resource_id=str(server.id),
                created_at=created,
                age=age,
                detail=f"status={getattr(server, 'status', '?')}" + ("" if eligible else " [TOO_YOUNG]"),
            )
        )
        if not eligible:
            hits[-1].detail = hits[-1].detail  # marker used below
    return hits


def _scan_keypairs(conn: Connection, min_age: timedelta, now: datetime) -> list[ResourceHit]:
    # Keypairs often lack created_at. Unknown-age keypairs are filtered later
    # (skipped unless --aggressive-keypairs or --min-age-hours 0).
    hits: list[ResourceHit] = []
    for key in conn.list_keypairs() or []:
        name = getattr(key, "name", None)
        if not _name_matches(name, NAME_PATTERNS):
            continue
        created = _parse_openstack_timestamp(getattr(key, "created_at", None))
        eligible, age = _age_ok(created, min_age, now)
        hits.append(
            ResourceHit(
                kind="keypair",
                name=name or "",
                resource_id=name or "",
                created_at=created,
                age=age,
                detail="" if eligible else "[TOO_YOUNG]",
            )
        )
    return hits


def _scan_images(conn: Connection, min_age: timedelta, now: datetime) -> list[ResourceHit]:
    hits: list[ResourceHit] = []
    # Prefer project-owned images; list_images may include public base images.
    for image in conn.list_images() or []:
        name = getattr(image, "name", None)
        # Do not touch public/shared marketplace images even if name collides.
        visibility = str(getattr(image, "visibility", "") or "").lower()
        if visibility in {"public", "community"}:
            continue
        if not _name_matches(name, NAME_PATTERNS):
            continue
        created = _parse_openstack_timestamp(getattr(image, "created_at", None))
        eligible, age = _age_ok(created, min_age, now)
        hits.append(
            ResourceHit(
                kind="image",
                name=name or "",
                resource_id=str(image.id),
                created_at=created,
                age=age,
                detail=f"status={getattr(image, 'status', '?')} visibility={visibility or '?'}"
                + ("" if eligible else " [TOO_YOUNG]"),
            )
        )
    return hits


def _scan_security_groups(conn: Connection, min_age: timedelta, now: datetime) -> list[ResourceHit]:
    hits: list[ResourceHit] = []
    for sg in conn.list_security_groups() or []:
        name = getattr(sg, "name", None)
        if not name or name in PROTECTED_EXACT_NAMES:
            continue
        if not _name_matches(name, SG_PATTERNS) and not _name_matches(name, NAME_PATTERNS):
            continue
        created = _parse_openstack_timestamp(getattr(sg, "created_at", None))
        eligible, age = _age_ok(created, min_age, now)
        hits.append(
            ResourceHit(
                kind="security_group",
                name=name,
                resource_id=str(sg.id),
                created_at=created,
                age=age,
                detail="" if eligible else "[TOO_YOUNG]",
            )
        )
    return hits


def _format_age(age: timedelta | None) -> str:
    if age is None:
        return "age=unknown"
    hours = age.total_seconds() / 3600.0
    if hours < 48:
        return f"age={hours:.1f}h"
    return f"age={hours / 24.0:.1f}d"


def _delete_hit(conn: Connection, hit: ResourceHit, wait_timeout: int) -> None:
    if hit.kind == "server":
        LOG.info("deleting server %s (%s)", hit.name, hit.resource_id)
        ok = conn.delete_server(hit.resource_id, wait=True, timeout=wait_timeout)
        if not ok:
            # Some SDK versions return False if already gone.
            if conn.get_server(hit.resource_id):
                raise RuntimeError(f"delete_server returned False for {hit.resource_id}")
    elif hit.kind == "keypair":
        LOG.info("deleting keypair %s", hit.name)
        conn.delete_keypair(hit.name)
    elif hit.kind == "image":
        LOG.info("deleting image %s (%s)", hit.name, hit.resource_id)
        conn.delete_image(hit.resource_id, wait=True)
    elif hit.kind == "security_group":
        LOG.info("deleting security_group %s (%s)", hit.name, hit.resource_id)
        conn.delete_security_group(hit.resource_id)
    else:
        raise ValueError(f"unknown kind {hit.kind}")


def _filter_eligible(
    hits: list[ResourceHit],
    min_age: timedelta,
    now: datetime,
    aggressive_keypairs: bool,
) -> tuple[list[ResourceHit], list[ResourceHit]]:
    """Split into (to_delete, skipped_young_or_policy)."""
    to_delete: list[ResourceHit] = []
    skipped: list[ResourceHit] = []
    for hit in hits:
        # Unknown age keypairs: only with aggressive flag, or when min_age is 0.
        if hit.kind == "keypair" and hit.created_at is None:
            if aggressive_keypairs or min_age.total_seconds() <= 0:
                to_delete.append(hit)
            else:
                hit.detail = (hit.detail + " [SKIP_UNKNOWN_AGE_KEYPAIR]").strip()
                skipped.append(hit)
            continue
        eligible, age = _age_ok(hit.created_at, min_age, now)
        hit.age = age
        if eligible:
            to_delete.append(hit)
        else:
            hit.detail = (hit.detail + " [TOO_YOUNG]").strip()
            skipped.append(hit)
    return to_delete, skipped


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Cleanup dangling OpenStack CI resources from github-runner and "
            "github-runner-image-builder integration tests."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matched resources. Without this flag, only list them.",
    )
    p.add_argument(
        "--min-age-hours",
        type=float,
        default=6.0,
        help=(
            "Only touch resources older than this many hours "
            "(default: 6). Avoids racing active CI. Keypairs without timestamps "
            "are skipped unless --aggressive-keypairs or min-age is 0."
        ),
    )
    p.add_argument(
        "--aggressive-keypairs",
        action="store_true",
        help="Delete matching keypairs even when created_at is unavailable.",
    )
    p.add_argument(
        "--kinds",
        default="server,keypair,image,security_group",
        help="Comma-separated resource kinds to consider (default: all).",
    )
    p.add_argument(
        "--os-cloud",
        default=os.environ.get("OS_CLOUD"),
        help="Cloud name from clouds.yaml (or OS_CLOUD).",
    )
    p.add_argument(
        "--clouds-file",
        default=None,
        help="Path to clouds.yaml if not in the default search path.",
    )
    p.add_argument(
        "--wait-timeout",
        type=int,
        default=300,
        help="Seconds to wait for server/image delete (default: 300).",
    )
    p.add_argument(
        "--max-deletes",
        type=int,
        default=0,
        help="Safety cap on deletes this run (0 = unlimited).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v, -vv).",
    )
    p.add_argument(
        "--json-summary",
        action="store_true",
        help="Print a machine-readable summary line on stdout at the end.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose >= 2 else logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Always show cleanup decisions at INFO when not quiet — promote default to INFO.
    if args.verbose == 0:
        logging.getLogger().setLevel(logging.INFO)

    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    valid = {"server", "keypair", "image", "security_group"}
    unknown = kinds - valid
    if unknown:
        LOG.error("unknown --kinds values: %s (valid: %s)", unknown, sorted(valid))
        return 2

    min_age = timedelta(hours=args.min_age_hours)
    now = datetime.now(tz=timezone.utc)

    try:
        conn = _connect(args)
    except Exception as exc:  # noqa: BLE001 - top-level auth failure
        LOG.error("failed to connect to OpenStack: %s", exc)
        return 2

    project = None
    try:
        project = conn.current_project_id
    except Exception:  # noqa: BLE001
        pass
    LOG.info(
        "connected project_id=%s cloud=%s apply=%s min_age_hours=%s kinds=%s",
        project,
        args.os_cloud or "(env/default)",
        args.apply,
        args.min_age_hours,
        ",".join(sorted(kinds)),
    )

    scanners: dict[str, Callable[[Connection, timedelta, datetime], list[ResourceHit]]] = {
        "server": _scan_servers,
        "keypair": _scan_keypairs,
        "image": _scan_images,
        "security_group": _scan_security_groups,
    }

    all_hits: list[ResourceHit] = []
    for kind in ("server", "keypair", "image", "security_group"):
        if kind not in kinds:
            continue
        try:
            hits = scanners[kind](conn, min_age, now)
        except Exception as exc:  # noqa: BLE001
            LOG.error("failed listing %s: %s", kind, exc)
            return 1
        all_hits.extend(hits)

    # Delete order: servers first (may hold SG/keypair refs), then images, keypairs, SGs.
    order = {"server": 0, "image": 1, "keypair": 2, "security_group": 3}
    all_hits.sort(key=lambda h: (order.get(h.kind, 9), h.name))

    to_delete, skipped = _filter_eligible(
        all_hits,
        min_age=min_age,
        now=now,
        aggressive_keypairs=args.aggressive_keypairs,
    )

    stats = Stats(considered=len(all_hits), matched=len(all_hits))

    for hit in skipped:
        stats.too_young += 1
        LOG.info(
            "SKIP %s name=%s id=%s %s %s",
            hit.kind,
            hit.name,
            hit.resource_id,
            _format_age(hit.age),
            hit.detail,
        )

    if args.max_deletes and len(to_delete) > args.max_deletes:
        LOG.warning(
            "truncating candidate list from %s to --max-deletes=%s",
            len(to_delete),
            args.max_deletes,
        )
        to_delete = to_delete[: args.max_deletes]

    mode = "DELETE" if args.apply else "DRY-RUN"
    for hit in to_delete:
        LOG.info(
            "%s %s name=%s id=%s %s %s",
            mode,
            hit.kind,
            hit.name,
            hit.resource_id,
            _format_age(hit.age),
            hit.detail,
        )
        if not args.apply:
            continue
        try:
            _delete_hit(conn, hit, wait_timeout=args.wait_timeout)
            stats.deleted += 1
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            LOG.error(
                "FAILED %s name=%s id=%s: %s",
                hit.kind,
                hit.name,
                hit.resource_id,
                exc,
            )

    LOG.info(
        "summary considered=%s candidates=%s skipped_young_or_policy=%s deleted=%s failed=%s apply=%s",
        stats.considered,
        len(to_delete),
        stats.too_young,
        stats.deleted,
        stats.failed,
        args.apply,
    )
    if args.json_summary:
        import json

        print(
            json.dumps(
                {
                    "project_id": project,
                    "apply": args.apply,
                    "min_age_hours": args.min_age_hours,
                    "considered": stats.considered,
                    "candidates": len(to_delete),
                    "skipped": stats.too_young,
                    "deleted": stats.deleted,
                    "failed": stats.failed,
                    "candidates_detail": [
                        {
                            "kind": h.kind,
                            "name": h.name,
                            "id": h.resource_id,
                            "age_seconds": None if h.age is None else h.age.total_seconds(),
                        }
                        for h in to_delete
                    ],
                }
            )
        )

    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass

    return 1 if stats.failed else 0


if __name__ == "__main__":
    sys.exit(main())
