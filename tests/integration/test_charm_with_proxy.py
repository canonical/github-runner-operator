#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    ensure_charm_has_runner,
    get_runner_names,
    run_in_lxd_instance,
)


@pytest_asyncio.fixture(scope="module", name="app_with_aproxy")
async def app_with_aproxy_fixture(model: Model, app_no_runner: Application, squid_proxy: str) -> Application:
    """Application configured to use aproxy"""

    await model.set_config(
        {
            "juju-http-proxy": squid_proxy,
            "juju-https-proxy": squid_proxy,
            "juju-no-proxy": "",
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    await app_no_runner.set_config({"use-aproxy": "true"})

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
