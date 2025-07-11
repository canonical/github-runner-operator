#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

import logging
import secrets
import socket
from typing import AsyncIterator

import pytest
import pytest_asyncio
from juju.application import Application
from pytest_httpserver import HTTPServer

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    PATH_CONFIG_NAME,
    RECONCILE_INTERVAL_CONFIG_NAME,
    TOKEN_CONFIG_NAME,
)
from tests.integration.conftest import DEFAULT_RECONCILE_INTERVAL
from tests.integration.helpers.common import wait_for_reconcile
from tests.integration.helpers.openstack import PrivateEndpointConfigs

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.openstack


@pytest_asyncio.fixture(scope="module", name="image_builder_config")
async def image_builder_config_fixture(
    private_endpoint_config: PrivateEndpointConfigs | None,
    flavor_name: str,
    network_name: str,
):
    """The image builder application default for OpenStack runners."""
    if not private_endpoint_config:
        raise ValueError("Private endpoints are required for testing OpenStack runners.")
    return {
        "build-interval": "12",
        "revision-history-limit": "2",
        "openstack-auth-url": private_endpoint_config["auth_url"],
        # Bandit thinks this is a hardcoded password
        "openstack-password": private_endpoint_config["password"],  # nosec: B105
        "openstack-project-domain-name": private_endpoint_config["project_domain_name"],
        "openstack-project-name": private_endpoint_config["project_name"],
        "openstack-user-domain-name": private_endpoint_config["user_domain_name"],
        "openstack-user-name": private_endpoint_config["username"],
        "build-flavor": flavor_name,
        "build-network": network_name,
        "architecture": "amd64",
        "script-url": "https://git.launchpad.net/job-manager/plain/scripts/post-image-build.sh?h=main",  # noqa
    }


@pytest.fixture(scope="session")
def httpserver_listen_port() -> int:
    # Do not use the listening port of the builder-agent, as it
    # will interfere with the tunnel from the runner to the mock jobmanager.
    return 8000


@pytest.fixture(scope="session")
def httpserver_listen_address(httpserver_listen_port: int):
    return ("0.0.0.0", httpserver_listen_port)


@pytest.fixture(scope="session", name="jobmanager_ip_address")
def jb_ip_address_fixture() -> str:
    """IP address for the jobmanager tests."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use as the fake jobmanager: %s", ip_address)
    s.close()
    return ip_address


@pytest.fixture(scope="session", name="jobmanager_base_url")
def jobmanager_base_url_fixture(
    jobmanager_ip_address: str,
    httpserver_listen_port: int,
) -> str:
    """Jobmanager base URL for the tests."""
    return f"http://{jobmanager_ip_address}:{httpserver_listen_port}"


@pytest.fixture(scope="session", name="jobmanager_token")
def jobmanager_token_fixture() -> str:
    """Token for the jobmanager tests."""
    return secrets.token_hex(8)


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    app_no_runner: Application,
    jobmanager_base_url: str,
    jobmanager_token: str,
    httpserver: HTTPServer,
) -> AsyncIterator[Application]:
    """Setup and tear down for app."""
    app_for_jobmanager = app_no_runner

    await app_for_jobmanager.set_config(
        {
            RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL),
            TOKEN_CONFIG_NAME: jobmanager_token,
            PATH_CONFIG_NAME: jobmanager_base_url,
        }
    )
    await wait_for_reconcile(app_for_jobmanager)

    httpserver.clear_all_handlers()

    yield app_for_jobmanager

    # cleanup of any runner spawned
    await app_for_jobmanager.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            RECONCILE_INTERVAL_CONFIG_NAME: str(DEFAULT_RECONCILE_INTERVAL),
        }
    )
    await wait_for_reconcile(app_for_jobmanager)
