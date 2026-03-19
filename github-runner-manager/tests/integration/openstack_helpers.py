# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""OpenStack helper functions shared by integration tests."""

import logging
import socket
import time
from pathlib import Path

import openstack
from github.Repository import Repository
from openstack.compute.v2.server import Server as OpenstackServer

from .factories import TestConfig

logger = logging.getLogger(__name__)


def wait_for_runner(
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    timeout: int = 300,
    interval: int = 5,
) -> tuple[OpenstackServer, str] | tuple[None, None]:
    """Wait for an OpenStack runner to be created and return it with its IP."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        servers = [
            server
            for server in openstack_connection.list_servers()
            if server.name.startswith(test_config.vm_prefix)
        ]
        if servers:
            runner = servers[0]
            logger.info("Found runner: %s", runner.name)

            ip = None
            for network_addresses in runner.addresses.values():
                for address in network_addresses:
                    ip = address["addr"]
                    break
                if ip:
                    break

            if ip:
                return runner, ip

        time.sleep(interval)

    return None, None


def wait_for_no_runners(
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    timeout: int = 900,
    interval: int = 15,
) -> bool:
    """Wait until no VMs with the test prefix exist on OpenStack."""
    start = time.time()
    while time.time() - start < timeout:
        servers = [
            server
            for server in openstack_connection.list_servers()
            if server.name.startswith(test_config.vm_prefix)
        ]
        if not servers:
            return True
        time.sleep(interval)
    return False


def wait_for_ssh(
    runner_ip: str,
    port: int = 22,
    timeout: int = 120,
    interval: int = 2,
    connect_timeout: int = 5,
) -> bool:
    """Wait for SSH port to become available on the runner."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((runner_ip, port), timeout=connect_timeout):
                logger.info("SSH port %d is now available on %s", port, runner_ip)
                return True
        except (socket.timeout, socket.error, OSError):
            time.sleep(interval)

    logger.error("SSH port %d never became available on %s", port, runner_ip)
    return False


def wait_for_runner_online(
    github_repository: Repository,
    runner_name: str,
    timeout: int = 10 * 60,
    interval: int = 30,
) -> None:
    """Wait for a runner to register as online on GitHub.

    The runner VM may exist in OpenStack but cloud-init and runner registration
    take additional time. This ensures the runner is fully initialized before
    the test proceeds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for runner in github_repository.get_self_hosted_runners():
            if runner.name == runner_name and runner.status == "online":
                logger.info("Runner %s is online on GitHub", runner_name)
                return
        time.sleep(interval)
    raise TimeoutError(f"Timeout waiting for runner {runner_name} to register online on GitHub")


def resolve_runner_ssh_key_path(
    runner: OpenstackServer,
) -> Path:
    """Resolve the local SSH private key path for an OpenStack runner."""
    return Path.home() / ".ssh" / f"{runner.name}.key"
