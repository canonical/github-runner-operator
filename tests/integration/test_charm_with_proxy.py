#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import subprocess
from asyncio import sleep
from typing import AsyncIterator

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    ensure_charm_has_runner,
    get_runner_names,
    run_in_lxd_instance,
)
from tests.status_name import ACTIVE_STATUS_NAME
from utilities import execute_command

PROXY_PORT = 8899


@pytest_asyncio.fixture(scope="module", name="proxy")
async def proxy_fixture() -> AsyncIterator[str]:
    """Start proxy.py and return the proxy server address."""
    process = subprocess.Popen(["proxy", "--hostname", "0.0.0.0", "--port", str(PROXY_PORT)])

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


@pytest_asyncio.fixture(scope="module", name="app_with_aproxy")
async def app_with_aproxy_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    proxy: str,
) -> Application:
    """Application with aproxy setup and firewall to block all other network access."""
    await model.set_config(
        {
            "juju-http-proxy": proxy,
            "juju-https-proxy": proxy,
            "juju-no-proxy": "",
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    machine = await model.add_machine(constraints={"root-disk": 15}, series="jammy")
    # Wait until juju agent has the hostname of the machine.
    for _ in range(60):
        if machine.hostname is not None:
            break
        await sleep(10)
    else:
        assert False, "Timeout waiting for machine to start"

    # Disable external network access for the juju machine.
    execute_command(["lxc", "config", "device", "add", machine.hostname, "eth0", "none"])
    # Test the external network access is disabled.
    await machine.ssh("ping -c1 canonical.com 2>&1 | grep 'Temporary failure in name resolution'")

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
            "experimental-use-aproxy": "true",
        },
        constraints={"root-disk": 15},
    )
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME, timeout=60 * 30)

    await ensure_charm_has_runner(app=application, model=model)

    return application


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_usage_of_aproxy(model: Model, app_with_aproxy: Application) -> None:
    """
    arrange: A working application with one runner using aproxy configured for a proxy server.
    act: Run curl in the runner.
    assert: The aproxy log contains the request.
    """
    await ensure_charm_has_runner(app_with_aproxy, model)
    unit = app_with_aproxy.units[0]
    names = await get_runner_names(unit)
    assert names
    runner_name = names[0]

    return_code, stdout = await run_in_lxd_instance(unit, runner_name, "curl http://canonical.com")
    assert return_code == 0

    return_code, stdout = await run_in_lxd_instance(
        unit, runner_name, "snap logs aproxy.aproxy -n=all"
    )
    assert return_code == 0
    assert stdout is not None
    assert "canonical.com" in stdout
