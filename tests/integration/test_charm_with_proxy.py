#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import subprocess
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
    model: Model, app_no_runner: Application, proxy: str
) -> Application:
    """Application configured to use aproxy"""

    await model.set_config(
        {
            "juju-http-proxy": proxy,
            "juju-https-proxy": proxy,
            "juju-no-proxy": "",
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    await app_no_runner.set_config({"experimental-use-aproxy": "true"})

    return app_no_runner


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
