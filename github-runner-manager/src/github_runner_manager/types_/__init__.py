# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Package containing modules with type definitions."""
from pydantic import BaseModel


class SystemUserConfig(BaseModel):
    """Configuration for which user to use when spawning processes or accessing resources.

    Attributes:
        user: The user to choose when spawning processes or accessing resources.
        group: The group to choose when spawning processes or accessing resources.
    """

    user: str
    group: str
