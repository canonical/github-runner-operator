# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import subprocess
from asyncio import sleep
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from juju.application import Application
from juju.machine import Machine
from juju.model import Model

from tests.integration.helpers import (
    ensure_charm_has_runner,
    get_runner_names,
    run_in_lxd_instance,
)
from tests.status_name import ACTIVE
from utilities import execute_command

NO_PROXY = "127.0.0.1,localhost,::1"
PROXY_PORT = 8899


@pytest_asyncio.fixture(scope="module", name="proxy")
async def proxy_fixture() -> AsyncIterator[str]:
    """Start tinyproxy and return the proxy server address."""
    result = subprocess.run(["which", "tinyproxy"])
    assert (
        result.returncode == 0
    ), "Cannot find tinyproxy in PATH, install tinyproxy with `apt install tinyproxy -y`"

    tinyproxy_config = Path("tinyproxy.conf")
    tinyproxy_config.write_text((f"Port {PROXY_PORT}\n" "Listen 0.0.0.0\n" "Timeout 600\n"))

    process = subprocess.Popen(["tinyproxy", "-d", "-c", str(tinyproxy_config)])

    # Get default ip using following commands
    stdout, _ = execute_command(
        [
            "/bin/bash",
            "-c",
            r"ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \K\S+') |"
            r" grep -oP 'src \K\S+'",
        ],
        check_exit=True,
    )
    default_ip = stdout.strip()

    yield f"http://{default_ip}:{PROXY_PORT}"

    process.terminate()
    if tinyproxy_config.exists():
        tinyproxy_config.unlink()


@pytest_asyncio.fixture(scope="module", name="prepared_machine")
async def prepared_machine_fixture(model: Model, proxy: str) -> Machine:
    await model.set_config(
        {
            "apt-http-proxy": proxy,
            "apt-https-proxy": proxy,
            "apt-no-proxy": NO_PROXY,
            "juju-http-proxy": proxy,
            "juju-https-proxy": proxy,
            "juju-no-proxy": NO_PROXY,
            "snap-http-proxy": proxy,
            "snap-https-proxy": proxy,
            "snap-no-proxy": NO_PROXY,
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    machine = await model.add_machine(constraints={"root-disk": 15}, series="jammy")
    # Wait until juju agent has the hostname of the machine.
    for _ in range(120):
        if machine.hostname is not None:
            break
        await sleep(10)
    else:
        assert False, "Timeout waiting for machine to start"

    # Disable external network access for the juju machine.
    proxy_url = urlparse(proxy)
    await machine.ssh(f"sudo iptables -I OUTPUT -d {proxy_url.hostname} -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 0.0.0.0/8 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 10.0.0.0/8 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 100.64.0.0/10 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 127.0.0.0/8 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 169.254.0.0/16 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 172.16.0.0/12 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 192.0.0.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 192.0.2.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 192.88.99.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 192.168.0.0/16 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 198.18.0.0/15 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 198.51.100.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 203.0.113.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 224.0.0.0/4 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 233.252.0.0/24 -j ACCEPT")
    await machine.ssh("sudo iptables -I OUTPUT -d 240.0.0.0/4 -j ACCEPT")
    await machine.ssh("sudo iptables -P OUTPUT DROP")
    # Test the external network access is disabled.
    await machine.ssh("ping -c1 canonical.com 2>&1 | grep '100% packet loss'")

    return machine


@pytest_asyncio.fixture(scope="module", name="app_with_aproxy")
async def app_with_aproxy_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    proxy: str,
    prepared_machine: Machine,
) -> Application:
    """Application with aproxy setup and firewall to block all other network access."""

    # Deploy the charm in the juju machine with external network access disabled.
    application = await model.deploy(
        charm_file,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "token": token,
            "virtual-machines": 1,
            "denylist": "10.10.0.0/16",
            "test-mode": "insecure",
            "reconcile-interval": 60,
            "experimental-use-aproxy": "true",
        },
        constraints={"root-disk": 15},
        to=prepared_machine.id,
    )
    await model.wait_for_idle(status=ACTIVE, timeout=60 * 60)

    return application


@pytest_asyncio.fixture(scope="module", name="app_without_aproxy")
async def app_without_aproxy_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    proxy: str,
    prepared_machine: Machine,
) -> Application:
    """Application with aproxy setup and firewall to block all other network access."""

    # Deploy the charm in the juju machine with external network access disabled.
    application = await model.deploy(
        charm_file,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "token": token,
            "virtual-machines": 1,
            "denylist": "10.10.0.0/16",
            "test-mode": "insecure",
            "reconcile-interval": 60,
            "experimental-use-aproxy": "false",
        },
        constraints={"root-disk": 15},
        to=prepared_machine.id,
    )
    await model.wait_for_idle(status=ACTIVE, timeout=60 * 60)

    return application


def _assert_proxy_var_in(text: str, not_in=False):
    """Assert that proxy environment variables are set / not set.

    Args:
        text: The text to search for proxy environment variables.
        not_in: Whether the proxy environment variables should be set or not.
    """
    for proxy_var in (
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    ):
        assert (proxy_var in text) != not_in


async def _assert_proxy_vars_in_file(unit, runner_name, file_path, not_set=False):
    """Assert that proxy environment variables are set / not set in a file.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
        file_path: The path to the file to check for proxy environment variables.
        not_set: Whether the proxy environment variables should be set or not.
    """
    return_code, stdout = await run_in_lxd_instance(unit, runner_name, f"cat {file_path}")
    assert return_code == 0, "Failed to read file"
    _assert_proxy_var_in(stdout, not_in=not_set)


async def _assert_docker_proxy_vars(unit, runner_name, not_set=False):
    """Assert that proxy environment variables are set / not set for docker.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
        not_set: Whether the proxy environment variables should be set or not.
    """
    return_code, _ = await run_in_lxd_instance(
        unit, runner_name, "docker run --rm alpine sh -c 'env | grep -i  _PROXY'"
    )
    assert return_code == (1 if not_set else 0)


async def _assert_proxy_vars(unit, runner_name, not_set=False):
    """Assert that proxy environment variables are set / not set in the runner.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
        not_set: Whether the proxy environment variables should be set or not.
    """
    await _assert_proxy_vars_in_file(unit, runner_name, "/etc/environment", not_set=not_set)
    await _assert_proxy_vars_in_file(
        unit, runner_name, "/home/ubuntu/github-runner/.env", not_set=not_set
    )
    await _assert_docker_proxy_vars(unit, runner_name, not_set=not_set)


async def _assert_proxy_vars_set(unit, runner_name):
    """Assert that proxy environment variables are set in the runner.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
    """
    await _assert_proxy_vars(unit, runner_name, not_set=False)


async def _assert_proxy_vars_not_set(unit, runner_name):
    """Assert that proxy environment variables are not set in the runner.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
    """
    await _assert_proxy_vars(unit, runner_name, not_set=True)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_usage_of_aproxy(model: Model, app_with_aproxy: Application) -> None:
    """
    arrange: A working application with one runner using aproxy configured for a proxy server.
    act: Run curl in the runner.
    assert: Check that no proxy vars are set in the runner and
        that the aproxy log contains the request.
    """
    await ensure_charm_has_runner(app_with_aproxy, model)
    unit = app_with_aproxy.units[0]
    names = await get_runner_names(unit)
    assert names
    runner_name = names[0]

    await _assert_proxy_vars_not_set(unit, runner_name)
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        "curl http://canonical.com",
    )

    assert return_code == 0

    return_code, stdout = await run_in_lxd_instance(
        unit, runner_name, "snap logs aproxy.aproxy -n=all"
    )
    assert return_code == 0
    assert stdout is not None
    assert "canonical.com" in stdout


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_use_proxy_without_aproxy(model: Model, app_without_aproxy: Application) -> None:
    """
    arrange: A working application with one runner configured for a proxy server
        and not using aproxy.
    act: Run curl in the runner.
    assert: Check that proxy vars are set and that the aproxy log does not contain the request.
    """
    await ensure_charm_has_runner(app_without_aproxy, model)
    unit = app_without_aproxy.units[0]
    names = await get_runner_names(unit)
    assert names
    runner_name = names[0]

    await _assert_proxy_vars_set(unit, runner_name)
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        "curl http://canonical.com",
    )

    assert return_code == 0

    return_code, stdout = await run_in_lxd_instance(
        unit, runner_name, "snap logs aproxy.aproxy -n=all"
    )
    assert return_code == 0
    assert stdout is not None
    assert "canonical.com" not in stdout
