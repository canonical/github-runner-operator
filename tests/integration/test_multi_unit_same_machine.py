# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm-level test: multiple units on the same machine.

Validates that two units co-located on a single machine each run their own
github-runner-manager instance service, allocate distinct HTTP ports, persist
those ports, and expose metrics endpoints.
"""

from pathlib import Path

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers.common import get_file_content, run_in_unit


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_multi_unit_same_machine_co_location(model: Model, app_openstack_runner: Application) -> None:
    """
    arrange: Have one deployed unit, find its machine, and add a second unit to the same machine.
    act: Verify per-unit systemd instance services, distinct/persisted ports, and metrics.
    assert: Both instance services are active; ports are distinct and persisted; metrics respond.
    """
    app = app_openstack_runner

    # Get machine id of the first unit
    unit0 = app.units[0]
    status = await model.get_status([app.name])
    app_status = status.applications[app.name]
    unit0_status = app_status.units[unit0.name]
    machine_id = unit0_status.machine

    # Add a second unit to the same machine and wait for it to settle
    await app.add_unit(to=machine_id)
    await model.wait_for_idle(apps=[app.name], status="active", timeout=20 * 60)

    # Refresh units reference (juju lib may not auto-refresh the list)
    status = await model.get_status([app.name])
    app_status = status.applications[app.name]
    unit_names = list(app_status.units.keys())
    assert len(unit_names) >= 2, "Expected at least two units after add-unit"

    # Work with the first two units
    u0_name, u1_name = unit_names[0], unit_names[1]
    unit_map = {u.name: u for u in app.units}
    unit0 = unit_map[u0_name]
    unit1 = unit_map[u1_name]

    # Instance service names
    inst0 = f"github-runner-manager@{u0_name.replace('/', '-')}"
    inst1 = f"github-runner-manager@{u1_name.replace('/', '-')}"

    # Services should be active
    rc, out, err = await run_in_unit(unit0, f"systemctl is-active {inst0}.service")
    assert rc == 0 and (out or "").strip() == "active", f"{inst0} not active: {out} {err}"
    rc, out, err = await run_in_unit(unit1, f"systemctl is-active {inst1}.service")
    assert rc == 0 and (out or "").strip() == "active", f"{inst1} not active: {out} {err}"

    # Read persisted ports for each unit
    port_file0 = Path(f"/var/lib/github-runner-manager/{u0_name.replace('/', '-')}/http_port")
    port_file1 = Path(f"/var/lib/github-runner-manager/{u1_name.replace('/', '-')}/http_port")
    p0 = int((await get_file_content(unit0, port_file0)))
    p1 = int((await get_file_content(unit1, port_file1)))
    assert p0 != p1, f"Expected distinct ports, got {p0} and {p1}"

    # Metrics endpoint should respond on both ports
    rc, _, err = await run_in_unit(unit0, f"curl -sf http://127.0.0.1:{p0}/metrics | head -n 1")
    assert rc == 0, f"Metrics not responding on unit0:{p0} - {err}"
    rc, _, err = await run_in_unit(unit1, f"curl -sf http://127.0.0.1:{p1}/metrics | head -n 1")
    assert rc == 0, f"Metrics not responding on unit1:{p1} - {err}"

    # Restart instance service on unit1 and verify persisted port doesn't change
    before = int((await get_file_content(unit1, port_file1)))
    await run_in_unit(unit1, f"sudo systemctl restart {inst1}.service", assert_on_failure=True)
    rc, out, err = await run_in_unit(unit1, f"systemctl is-active {inst1}.service")
    assert rc == 0 and (out or "").strip() == "active", f"{inst1} not active after restart: {out} {err}"
    after = int((await get_file_content(unit1, port_file1)))
    assert before == after, "Persisted port changed after restart"
