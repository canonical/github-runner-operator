# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import ActiveStatus, BlockedStatus

# mypy can not find type of `name` attribute.
ACTIVE_STATUS_NAME = ActiveStatus.name  # type: ignore
BLOCK_STATUS_NAME = BlockedStatus.name  # type: ignore
