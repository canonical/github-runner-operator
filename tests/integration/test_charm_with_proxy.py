# Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import logging
import subprocess
from asyncio import sleep
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
    reconcile,
    run_in_lxd_instance,
)
from tests.status_name import ACTIVE
from utilities import execute_command

NO_PROXY = "127.0.0.1,localhost,::1"
PROXY_PORT = 8899
NON_STANDARD_PORT = 9432


@pytest.fixture(scope="module", name="proxy_logs_filepath")
def proxy_logs_filepath_fixture(tmp_path_factory) -> Path:
    """Get the path to the proxy logs file."""
    return tmp_path_factory.mktemp("tinyproxy") / "tinyproxy.log"


@pytest_asyncio.fixture(scope="module", name="proxy")
async def proxy_fixture(proxy_logs_filepath: Path) -> AsyncIterator[str]:
    """Start tinyproxy and return the proxy server address."""
    result = subprocess.run(["which", "tinyproxy"])
    assert (
        result.returncode == 0
    ), "Cannot find tinyproxy in PATH, install tinyproxy with `apt install tinyproxy -y`"

    tinyproxy_config = Path("tinyproxy.conf")
    tinyproxy_config_value = f"""Port {PROXY_PORT}
Listen 0.0.0.0
Timeout 600
LogFile "{proxy_logs_filepath}"
LogLevel Connect
"""

    logging.info("tinyproxy config: %s", tinyproxy_config_value)
    tinyproxy_config.write_text(tinyproxy_config_value)

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

    # Ensure iptables rules are restored on reboot, which might happen during the test.
    await machine.ssh("sudo iptables-save | sudo tee /etc/iptables.rules.v4")
    await machine.ssh(
        """cat <<EOT | sudo tee /etc/systemd/system/iptables-restore.service
[Unit]
Description=Apply iptables firewall rules

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables.rules.v4
ExecReload=/sbin/iptables-restore /etc/iptables.rules.v4

[Install]
WantedBy=multi-user.target
EOT"""
    )
    await machine.ssh("sudo systemctl enable iptables-restore.service")

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


def _clear_tinyproxy_log(proxy_logs_filepath: Path) -> None:
    """Clear the tinyproxy log file content.

    Args:
        proxy_logs_filepath: The path to the tinyproxy log file.
    """
    proxy_logs_filepath.write_text("")


@pytest_asyncio.fixture(scope="function", name="app")
async def app_fixture(
    app_with_prepared_machine: Application, model: Model, proxy_logs_filepath: Path
) -> AsyncIterator[Application]:
    """Setup and teardown the app.

    Make sure before each test:
    - no runner exists
    - Proxy logs are cleared
    """
    await app_with_prepared_machine.set_config(
        {
            "virtual-machines": "0",
        }
    )
    await reconcile(app=app_with_prepared_machine, model=model)

    _clear_tinyproxy_log(proxy_logs_filepath)

    yield app_with_prepared_machine


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


async def _curl_as_ubuntu_user(unit: Unit, runner_name: str, url: str) -> tuple[int, str]:
    """Run curl as a logged in ubuntu user.

    This should simulate the bevahiour of a curl inside the runner with environment variables set.

    Args:
        unit: The unit to run the command on.
        runner_name: The name of the runner.
        url: The URL to curl.

    Returns:
        The return code and stdout of the curl command.
    """
    return await run_in_lxd_instance(
        unit,
        runner_name,
        f"su - ubuntu -c 'curl {url}'",
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_usage_of_aproxy(model: Model, app: Application, proxy_logs_filepath: Path) -> None:
    """
    arrange: A working application with a runner using aproxy configured for a proxy server.
    act: Run curl in the runner
        1. URL with standard port
        2. URL with non-standard port
    assert: That no proxy vars are set in the runner and that
        1. the aproxy and tinyproxy log contains the request
        2. neither the aproxy nor the tinyproxy log contains the request
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

    # Clear the logs to avoid false positives if the log already contains matching requests
    _clear_tinyproxy_log(proxy_logs_filepath)

    # 1. URL with standard port, should succeed, gets intercepted by aproxy
    return_code, stdout = await _curl_as_ubuntu_user(unit, runner_name, "http://canonical.com")
    assert (
        return_code == 0
    ), f"Expected successful connection to http://canonical.com. Error msg: {stdout}"

    # 2. URL with non-standard port, should fail, request does not get intercepted by aproxy
    return_code, stdout = await _curl_as_ubuntu_user(
        unit,
        runner_name,
        f"http://canonical.com:{NON_STANDARD_PORT}",
    )
    assert (
        return_code == 7
    ), f"Expected cannot connect error for http://canonical.com:{NON_STANDARD_PORT}. Error msg: {stdout}"

    aproxy_logs = await _get_aproxy_logs(unit, runner_name)
    assert aproxy_logs is not None
    assert "canonical.com" in aproxy_logs
    assert f"http://canonical.com:{NON_STANDARD_PORT}" not in aproxy_logs

    proxy_logs = proxy_logs_filepath.read_text(encoding="utf-8")
    assert "GET http://canonical.com/" in proxy_logs
    assert f"GET http://canonical.com:{NON_STANDARD_PORT}/" not in proxy_logs


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_use_proxy_without_aproxy(
    model: Model, app: Application, proxy_logs_filepath: Path
) -> None:
    """
    arrange: A working application with a runner not using aproxy configured for a proxy server.
    act: Run curl in the runner
        1. URL with standard port
        2. URL with non-standard port
    assert: That the proxy vars are set in the runner, aproxy logs are empty, and that
        the tinyproxy log contains both requests
        (requests to non-standard ports are forwared using env vars).
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

    # Clear the logs to avoid false positives if the log already contains matching requests
    _clear_tinyproxy_log(proxy_logs_filepath)

    # 1. URL with standard port, should succeed
    return_code, stdout = await _curl_as_ubuntu_user(unit, runner_name, "http://canonical.com")
    assert (
        return_code == 0
    ), f"Expected successful connection to http://canonical.com. Error msg: {stdout}"

    # 2. URL with non-standard port, should return an error message by the proxy like this:
    #
    #  <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
    # <html>
    # <head><title>500 Unable to connect</title></head>
    # <body>
    # <h1>Unable to connect</h1>
    # <p>Tinyproxy was unable to connect to the remote web server.</p>
    # <hr />
    # <p><em>Generated by tinyproxy version 1.11.0.</em></p>
    # </body>
    # </html>
    return_code, stdout = await _curl_as_ubuntu_user(
        unit,
        runner_name,
        f"http://canonical.com:{NON_STANDARD_PORT}",
    )
    assert (
        return_code == 0
    ), f"Expected error response from proxy for http://canonical.com:{NON_STANDARD_PORT}. Error msg: {stdout}"

    proxy_logs = proxy_logs_filepath.read_text(encoding="utf-8")
    assert "GET http://canonical.com/" in proxy_logs
    assert f"GET http://canonical.com:{NON_STANDARD_PORT}/" in proxy_logs

    aproxy_logs = await _get_aproxy_logs(unit, runner_name)
    assert aproxy_logs is None
