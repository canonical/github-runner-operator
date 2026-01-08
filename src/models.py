# Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Data classes and type definitions."""
import dataclasses
from typing import TypedDict

from pydantic import AnyHttpUrl


class AnyHttpsUrl(AnyHttpUrl):
    """Represents an HTTPS URL.

    Attributes:
        allowed_schemes: Allowed schemes for the URL.
    """

    allowed_schemes = {"https"}


class _OpenStackAuth(TypedDict):
    """The OpenStack cloud connection authentication info.

    Attributes:
        auth_url: The OpenStack authentication URL (keystone).
        password: The OpenStack project user's password.
        project_domain_name: The project domain in which the project belongs to.
        project_name: The OpenStack project to connect to.
        user_domain_name: The user domain in which the user belongs to.
        username: The user to authenticate as.
    """

    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str


class _OpenStackCloud(TypedDict):
    """The OpenStack cloud connection info.

    See https://docs.openstack.org/python-openstackclient/pike/configuration/index.html.

    Attributes:
        auth: The connection authentication info.
        region_name: The OpenStack region to authenticate to.
    """

    auth: _OpenStackAuth
    region_name: str


class OpenStackCloudsYAML(TypedDict):
    """The OpenStack clouds YAML dict mapping.

    Attributes:
        clouds: The map of cloud name to cloud connection info.
    """

    clouds: dict[str, _OpenStackCloud]


@dataclasses.dataclass
class FlavorLabel:
    """Combination of flavor and label.

    Attributes:
        flavor: Flavor for the VM.
        label: Label associated with the flavor.
    """

    flavor: str
    # Remove the None when several FlavorLabel combinations are supported.
    label: str | None
