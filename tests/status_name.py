# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import ActiveStatus, BlockedStatus

# mypy can not find type of `name` attribute.
ACTIVE = ActiveStatus.name  # type: ignore
BLOCKED = BlockedStatus.name  # type: ignore
