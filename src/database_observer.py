#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for observing events related to the database."""


import ops

from charms.data_platform_libs.v0.data_interfaces import \
    DatabaseCreatedEvent


class DatabaseObserver(ops.Object):
    """The Database relation observer."""

    def __init__(self, charm: ops.CharmBase, database_name: str):
        """Initialize the observer and register event handlers.

        Args:
            charm (ops.CharmBase): The charm instance
            database_name (str): The name of the database
        """

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """Handle the created database

        Args:
            event (DatabaseCreatedEvent): The event object
        """

    def _on_endpoints_changed(self, event: DatabaseCreatedEvent) -> None:
        """Handle the endpoints changed event

        Args:
            event (DatabaseCreatedEvent): The event object
        """


