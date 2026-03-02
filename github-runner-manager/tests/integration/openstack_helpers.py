# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""OpenStack helper functions shared by integration tests."""

import logging
import time
from pathlib import Path

import openstack
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


def resolve_runner_ssh_key_path(
    runner: OpenstackServer,
    key_dir: Path | None = None,
) -> Path:
    """Resolve the local SSH private key path for an OpenStack runner.

    The manager writes keypairs under ``~/.ssh/<key_name>.key`` where ``key_name``
    is usually the OpenStack keypair name. Fallbacks are included to make test
    failures easier to diagnose when naming differs.
    """
    key_dir = key_dir or (Path.home() / ".ssh")
    key_name = getattr(runner, "key_name", None)
    candidate_names = []
    if key_name:
        candidate_names.append(key_name)
    candidate_names.append(runner.name)

    for name in candidate_names:
        path = key_dir / f"{name}.key"
        if path.exists():
            return path

    runner_tokens = {token for token in candidate_names if token}
    for path in key_dir.glob("*.key"):
        if any(token in path.stem for token in runner_tokens):
            return path

    raise FileNotFoundError(
        f"Unable to find SSH key for runner {runner.name}. Looked in {key_dir} "
        f"for keys matching {candidate_names}."
    )
