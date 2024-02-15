# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import socketserver
import subprocess
import threading
from asyncio import sleep
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from tests.integration.helpers import (
    ensure_charm_has_runner,
    get_runner_names,
    run_in_lxd_instance,
)
from tests.status_name import ACTIVE
from utilities import execute_command

NO_PROXY = "127.0.0.1,localhost,::1"
NON_PRIVATE_IP = "200.100.100.10"
PROXY_PORT = 8899
HTTP_SERVER_PORT = 9432


@pytest.fixture(scope="module", name="host_ip")
def host_ip_fixture() -> str:
    """Get the default ip of the host."""
    stdout, _ = execute_command(
        [
            "/bin/bash",
            "-c",
            r"ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \K\S+') |"
            r" grep -oP 'src \K\S+'",
        ],
        check_exit=True,
    )
    return stdout.strip()


@pytest_asyncio.fixture(scope="module", name="proxy")
async def proxy_fixture(host_ip: str) -> AsyncIterator[str]:
    """Start tinyproxy and return the proxy server address."""
    result = subprocess.run(["which", "tinyproxy"])
    assert (
        result.returncode == 0
    ), "Cannot find tinyproxy in PATH, install tinyproxy with `apt install tinyproxy -y`"

    tinyproxy_config = Path("tinyproxy.conf")
    tinyproxy_config.write_text((f"Port {PROXY_PORT}\n" "Listen 0.0.0.0\n" "Timeout 600\n"))

    process = subprocess.Popen(["tinyproxy", "-d", "-c", str(tinyproxy_config)])

    yield f"http://{host_ip}:{PROXY_PORT}"

    process.terminate()
    if tinyproxy_config.exists():
        tinyproxy_config.unlink()


@pytest_asyncio.fixture(scope="module", name="http_server")
async def http_server(host_ip: str) -> AsyncIterator[str]:
    """Start a simple http server and return the address."""

    def start_http_server(port):
        handler = SimpleHTTPRequestHandler
        httpd = socketserver.TCPServer(("", port), handler)
        print(f"Serving on port {port}")
        httpd.serve_forever()

    # Start the server in a separate thread so it doesn't block the main thread
    t = threading.Thread(target=start_http_server, args=(HTTP_SERVER_PORT,), daemon=True)
    t.start()

    yield f"http://{host_ip}:{HTTP_SERVER_PORT}"


@pytest_asyncio.fixture(scope="module", name="app_with_prepared_machine")
async def app_with_prepared_machine_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    proxy: str,
) -> Application:
    """Application with proxy setup and firewall to block all other network access."""

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
    # Forbid direct access to http server
    await machine.ssh(
        "sudo iptables -A OUTPUT"
        f" -p tcp -d {proxy_url.hostname} --dport {HTTP_SERVER_PORT} -j DROP"
    )
    # Allow other access to the host , e.g. to the proxy
    await machine.ssh(f"sudo iptables -I OUTPUT -d {proxy_url.hostname} -j ACCEPT")
    # Explicitly allow access to the following networks.
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
    # Block all other network access.
    await machine.ssh("sudo iptables -P OUTPUT DROP")
    # Test the external network access is disabled.
    await machine.ssh("ping -c1 canonical.com 2>&1 | grep '100% packet loss'")

    # Deploy the charm in the juju machine with external network access disabled.
    application = await model.deploy(
        charm_file,
        application_name=app_name,
        series="jammy",
        config={
            "path": path,
            "token": token,
            "virtual-machines": 0,
            "denylist": "10.10.0.0/16",
            "test-mode": "insecure",
            "reconcile-interval": 60,
        },
        constraints={"root-disk": 15},
        to=machine.id,
    )
    await model.wait_for_idle(status=ACTIVE, timeout=60 * 60)

    return application


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(app_with_prepared_machine: Application) -> AsyncIterator[Application]:
    """Setup and teardown the app.

    Remove the runner after each test.
    """
    yield app_with_prepared_machine
    await app_with_prepared_machine.set_config(
        {
            "virtual-machines": 0,
        }
    )


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


async def _assert_proxy_vars_in_file(unit: Unit, runner_name: str, file_path: str, not_set=False):
    """Assert that proxy environment variables are set / not set in a file.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
        file_path: The path to the file to check for proxy environment variables.
        not_set: Whether the proxy environment variables should be set or not.
    """
    return_code, stdout = await run_in_lxd_instance(unit, runner_name, f"cat {file_path}")
    assert return_code == 0, "Failed to read file"
    assert stdout, "File is empty"
    _assert_proxy_var_in(stdout, not_in=not_set)


async def _assert_docker_proxy_vars(unit: Unit, runner_name: str, not_set=False):
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


async def _assert_proxy_vars(unit: Unit, runner_name: str, not_set=False):
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


async def _assert_proxy_vars_set(unit: Unit, runner_name: str):
    """Assert that proxy environment variables are set in the runner.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
    """
    await _assert_proxy_vars(unit, runner_name, not_set=False)


async def _assert_proxy_vars_not_set(unit: Unit, runner_name: str):
    """Assert that proxy environment variables are not set in the runner.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
    """
    await _assert_proxy_vars(unit, runner_name, not_set=True)


async def _add_translation_of_non_private_ip(unit: Unit, runner_name: str, host_ip: str):
    """Add dnat rule to translate non-private ip to the host ip.

    Args:
        host_ip: The host ip.
        runner_name: The name of the runner.
        unit: The unit to run the command on.
    """
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        "sudo nft add rule nat OUTPUT"
        f" ip daddr 200.100.100.1 tcp dport {HTTP_SERVER_PORT} dnat to {host_ip}",
    )
    assert return_code == 0, f"Failed to add dnat rule: {stdout}"


async def _get_aproxy_logs(unit: Unit, runner_name: str) -> Optional[str]:
    """Get the aproxy logs.

    Args:
        runner_name: The name of the runner.
        unit: The unit to run the command on.

    Returns:
        The aproxy logs if existent, otherwise None.
    """
    return_code, stdout = await run_in_lxd_instance(
        unit, runner_name, "snap logs aproxy.aproxy -n=all"
    )
    assert return_code == 0, "Failed to get aproxy logs"
    return stdout


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_usage_of_aproxy(
    model: Model, app: Application, http_server: str, host_ip: str
) -> None:
    """
    arrange: A working application with a runner using aproxy configured for a proxy server.
        A non-private IP (X) is translated to the host IP that a web server is listening on,
        so that aproxy has a chance to intercept the request.
    act: Run curl in the runner
        1. URL with standard port
        2. URL with non-private IP X with non-standard port
    assert: That no proxy vars are set in the runner and that
        1. the request is successful and the aproxy log contains the request
        2. the request is not successful and the aproxy log does not contain the request
    """
    await app.set_config(
        {
            "experimental-use-aproxy": "true",
        }
    )
    await ensure_charm_has_runner(app, model)
    unit = app.units[0]
    names = await get_runner_names(unit)
    assert names
    runner_name = names[0]

    await _add_translation_of_non_private_ip(unit, runner_name, host_ip)

    # 1. URL with standard port, should succeed, gets intercepted by aproxy
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        "curl http://canonical.com",
    )
    assert return_code == 0, f"Expected successful connection to http://canonical.com: {stdout}"

    # 2. URL with non-private IP X with non-standard port, should fail,
    # does not get intercepted by aproxy
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        f"curl --connect-timeout 1 {http_server}",
    )
    assert return_code == 28, f"Expected connect timeout to {http_server}: {stdout}"

    aproxy_logs = await _get_aproxy_logs(unit, runner_name)
    assert aproxy_logs is not None
    assert "canonical.com" in aproxy_logs
    assert NON_PRIVATE_IP not in aproxy_logs


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_use_proxy_without_aproxy(
    model: Model, app: Application, http_server, host_ip
) -> None:
    """
    arrange: A working application with a runner not using aproxy configured for a proxy server.
        A non-private IP (X) is translated to the host IP that a web server is listening on,
        so that aproxy has a chance to intercept the request.
    act: Run curl in the runner
        1. URL with standard port
        2. URL with non-private IP X with non-standard port
    assert: That the proxy vars are set in the runner, aproxy logs are empty, and that
        1. the request is successful
        2. the request is also successful because
            when using env vars requests to non-standard ports are also forwarded to the proxy
    """
    await app.set_config(
        {
            "experimental-use-aproxy": "false",
        }
    )
    await ensure_charm_has_runner(app, model)
    unit = app.units[0]
    names = await get_runner_names(unit)
    assert names
    runner_name = names[0]

    await _assert_proxy_vars_set(unit, runner_name)
    await _add_translation_of_non_private_ip(unit, runner_name, host_ip)

    # 1. URL with standard port, should succeed
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        "curl http://canonical.com",
    )
    assert return_code == 0, f"Expected successful connection to http://canonical.com: {stdout}"

    # 2. URL with non-private IP X with non-standard port, should succeed
    return_code, stdout = await run_in_lxd_instance(
        unit,
        runner_name,
        f"curl --connect-timeout 10 {http_server}",
    )
    assert return_code == 0, f"Expected successful connection to {http_server}"

    aproxy_logs = await _get_aproxy_logs(unit, runner_name)
    assert aproxy_logs is None
