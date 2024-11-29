# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for OpenStack objects."""

import factory
import openstack.compute.v2.server


class ServerFactory(factory.Factory):
    """Factory class for OpenStack server.

    Attributes:
        addresses: The OpenStack server addresses mapping.
        created_at: The datetime string in which the server was created.
        id: The OpenStack server UUID.
        name: The OpenStack server name.
        status: The server status.
    """

    class Meta:
        """Meta class for OpenStack server.

        Attributes:
            model: The metadata reference model.
        """

        model = openstack.compute.v2.server.Server

    name = "test-server"
    addresses = {
        "test-network-name": [
            {
                "version": 4,
                "addr": "10.145.236.69",
            }
        ]
    }
    created_at = "2024-09-12T02:48:03Z"
    id = "e6117e39-fbb4-47bc-9461-3933f5ab6f56"
    status = "ACTIVE"
