# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing OpenStack Configuration."""


from pydantic import BaseModel


class OpenStackConfiguration(BaseModel):
    """OpenStack configuration.

    Attributes:
        vm_prefix: Prefix to use for the instances managed by this application.
        network: Network to use to spawn instances.
        credentials: OpenStack credentials.
    """

    vm_prefix: str
    network: str
    credentials: "OpenStackCredentials"


class OpenStackCredentials(BaseModel):
    """OpenStack credentials.

    Attributes:
       auth_url: The auth url of the OpenStack host.
       project_name: The project name to log in to.
       username: The username to login with.
       password: The password to login with.
       user_domain_name: The domain name containing the user.
       project_domain_name: The domain name containing the project.
       region_name: The region.
    """

    auth_url: str
    project_name: str
    username: str
    password: str
    user_domain_name: str
    project_domain_name: str
    region_name: str


OpenStackConfiguration.update_forward_refs()
OpenStackCredentials.update_forward_refs()
