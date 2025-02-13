# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""TODO Module containing Configuration."""

import dataclasses


@dataclasses.dataclass
class OpenStackConfiguration:
    """TODO.

    Attributes:
        vm_prefix: TODO
        network: TODO
        credentials: TODO
    """

    vm_prefix: str
    network: str
    credentials: "OpenStackCredentials"


@dataclasses.dataclass
class OpenStackCredentials:
    """TODO.

    Attributes:
       auth_url: TODO
       project_name: TODO
       username: TODO
       password: TODO
       user_domain_name: TODO
       project_domain_name: TODO
       region_name: TODO
    """

    auth_url: str
    project_name: str
    username: str
    password: str
    user_domain_name: str
    project_domain_name: str
    region_name: str
