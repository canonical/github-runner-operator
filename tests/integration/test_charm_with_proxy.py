#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Test the usage of a proxy server."""
import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers import (
    ensure_charm_has_runner,
    get_runner_names,
    run_in_lxd_instance,
)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_usage_of_aproxy(model: Model, app_no_runner: Application, squid_proxy: str) -> None:
    """
    arrange: A working application with one runner using aproxy configured for a proxy server.
    act: Run curl in the runner.
    assert: The aproxy log contains the request.
    """
    app = app_no_runner  # Rename to make it clear that the app will contain a runner.
    unit = app.units[0]

    await model.set_config(
        {
            "juju-http-proxy": squid_proxy,
            "juju-https-proxy": squid_proxy,
            "juju-no-proxy": "",
            "logging-config": "<root>=INFO;unit=DEBUG",
        }
    )

    await app.set_config({"use-aproxy": "true"})
    await ensure_charm_has_runner(app, model)

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
