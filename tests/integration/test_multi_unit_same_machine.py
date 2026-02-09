# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm-level test: multiple units on the same machine.

Validates that two units co-located on a single machine each run their own
github-runner-manager instance service, allocate distinct HTTP ports, persist
those ports, and expose metrics endpoints.

Also validates that systemd service cgroup cleanup (ExecStopPost) works correctly
on restart, preventing leftover processes, port conflicts, and ensuring unit isolation.
"""

import asyncio
from pathlib import Path

import pytest
from juju.application import Application
from juju.model import Model

from tests.integration.helpers.common import get_file_content, run_in_unit


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_multi_unit_same_machine_co_location(
    model: Model, app_openstack_runner: Application
) -> None:
    """
    arrange: Have one deployed unit, find its machine, and add a second unit to the same machine.
    act: Verify per-unit systemd instance services, distinct/persisted ports, and metrics.
    assert: Both instance services are active; ports are distinct and persisted; metrics respond.
    """
    app = app_openstack_runner

    # Get machine id of the first unit
    unit0 = app.units[0]
    status = await model.get_status([app.name])
    app_status = status.applications.get(app.name)
    assert app_status is not None, "Application status missing for deployed app"
    unit0_status = app_status.units.get(unit0.name)
    assert unit0_status is not None, "Unit status missing for first unit"
    machine_id = unit0_status.machine

    # Add a second unit to the same machine and wait for it to settle
    await app.add_unit(to=machine_id)
    await model.wait_for_idle(apps=[app.name], status="active", timeout=20 * 60)

    # Refresh units reference (juju lib may not auto-refresh the list)
    status = await model.get_status([app.name])
    app_status = status.applications.get(app.name)
    assert app_status is not None, "Application status missing after add-unit"
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
    assert (
        rc == 0 and (out or "").strip() == "active"
    ), f"{inst1} not active after restart: {out} {err}"
    after = int((await get_file_content(unit1, port_file1)))
    assert before == after, "Persisted port changed after restart"


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_service_cgroup_cleanup_on_restart(
    model: Model, app_openstack_runner: Application
) -> None:
    """Verify cgroup cleanup works correctly on service restart.

    arrange: Deploy a unit with github-runner-manager service running.
    act: Restart the service and check for leftover processes.
    assert: Service restarts cleanly with no cgroup warnings or port conflicts.
    """
    app = app_openstack_runner
    unit = app.units[0]
    unit_name = unit.name
    instance = unit_name.replace("/", "-")
    service_name = f"github-runner-manager@{instance}.service"

    # Get the persisted HTTP port
    port_file = Path(f"/var/lib/github-runner-manager/{instance}/http_port")
    http_port = int((await get_file_content(unit, port_file)))

    # Verify service is active and responding before restart
    rc, out, err = await run_in_unit(unit, f"systemctl is-active {service_name}")
    assert rc == 0 and (out or "").strip() == "active", f"Service not active: {out} {err}"
    rc, _, _ = await run_in_unit(unit, f"curl -sf http://127.0.0.1:{http_port}/metrics")
    assert rc == 0, f"HTTP server not responding on port {http_port}"

    # Get the main process PID before restart
    rc, pid_before, _ = await run_in_unit(
        unit, f"systemctl show {service_name} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get MainPID"
    pid_before = (pid_before or "").strip()

    # Restart the service
    await run_in_unit(unit, f"sudo systemctl restart {service_name}", assert_on_failure=True)
    await asyncio.sleep(5)

    # Verify service is active after restart
    rc, out, err = await run_in_unit(unit, f"systemctl is-active {service_name}")
    assert rc == 0 and (out or "").strip() == "active", f"Service not active after restart: {err}"

    # Verify HTTP server is responding on the same port (no conflict)
    rc, _, _ = await run_in_unit(
        unit, f"curl -sf http://127.0.0.1:{http_port}/metrics", assert_on_failure=True
    )

    # Check systemd logs for "left-over process" warnings during the restart
    rc, journal_output, _ = await run_in_unit(
        unit,
        f"sudo journalctl -u {service_name} --since '2 minutes ago' | "
        f"grep -i 'left-over process' || true",
    )
    leftover_warnings = (journal_output or "").strip()
    assert (
        not leftover_warnings
    ), f"Found 'left-over process' warnings in systemd logs:\n{leftover_warnings}"

    # Verify the PID changed (service actually restarted)
    rc, pid_after, _ = await run_in_unit(
        unit, f"systemctl show {service_name} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get MainPID after restart"
    pid_after = (pid_after or "").strip()
    assert pid_after != pid_before, "PID should have changed after restart"

    # Verify port didn't change after restart (persisted correctly)
    http_port_after = int((await get_file_content(unit, port_file)))
    assert http_port == http_port_after, "HTTP port changed after restart"


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_service_cleanup_isolated_per_unit(
    model: Model, app_openstack_runner: Application
) -> None:
    """Verify service cleanup is isolated per unit on the same machine.

    arrange: Deploy two units on the same machine.
    act: Restart one unit's service while the other is running.
    assert: Only the restarted unit is affected; the other unit continues uninterrupted.
    """
    app = app_openstack_runner

    # Get machine id of the first unit
    unit0 = app.units[0]
    status = await model.get_status([app.name])
    app_status = status.applications.get(app.name)
    assert app_status is not None, "Application status missing for deployed app"
    unit0_status = app_status.units.get(unit0.name)
    assert unit0_status is not None, "Unit status missing for first unit"
    machine_id = unit0_status.machine

    # Add a second unit to the same machine
    await app.add_unit(to=machine_id)
    await model.wait_for_idle(apps=[app.name], status="active", timeout=20 * 60)

    # Refresh units reference
    status = await model.get_status([app.name])
    app_status = status.applications.get(app.name)
    assert app_status is not None, "Application status missing after add-unit"
    unit_names = list(app_status.units.keys())
    assert len(unit_names) >= 2, "Expected at least two units after add-unit"

    # Work with the first two units
    u0_name, u1_name = unit_names[0], unit_names[1]
    unit_map = {u.name: u for u in app.units}
    unit0 = unit_map[u0_name]
    unit1 = unit_map[u1_name]

    # Service names
    inst0 = f"github-runner-manager@{u0_name.replace('/', '-')}"
    inst1 = f"github-runner-manager@{u1_name.replace('/', '-')}"
    service0 = f"{inst0}.service"
    service1 = f"{inst1}.service"

    # Get PIDs of both services before restart
    rc, pid0_before, _ = await run_in_unit(
        unit0, f"systemctl show {service0} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get unit0 MainPID"
    pid0_before = (pid0_before or "").strip()

    rc, pid1_before, _ = await run_in_unit(
        unit1, f"systemctl show {service1} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get unit1 MainPID"
    pid1_before = (pid1_before or "").strip()

    # Get HTTP ports
    port_file0 = Path(f"/var/lib/github-runner-manager/{u0_name.replace('/', '-')}/http_port")
    port_file1 = Path(f"/var/lib/github-runner-manager/{u1_name.replace('/', '-')}/http_port")
    port0 = int((await get_file_content(unit0, port_file0)))
    port1 = int((await get_file_content(unit1, port_file1)))

    # Both services should be responding
    rc, _, _ = await run_in_unit(unit0, f"curl -sf http://127.0.0.1:{port0}/metrics")
    assert rc == 0, f"unit0 HTTP server not responding on port {port0}"
    rc, _, _ = await run_in_unit(unit1, f"curl -sf http://127.0.0.1:{port1}/metrics")
    assert rc == 0, f"unit1 HTTP server not responding on port {port1}"

    # Restart ONLY unit1's service
    await run_in_unit(unit1, f"sudo systemctl restart {service1}", assert_on_failure=True)
    await asyncio.sleep(5)

    # Verify unit1's service restarted (PID changed)
    rc, pid1_after, _ = await run_in_unit(
        unit1, f"systemctl show {service1} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get unit1 MainPID after restart"
    pid1_after = (pid1_after or "").strip()
    assert pid1_after != pid1_before, "unit1 PID should have changed after restart"

    # Verify unit0's service was NOT affected (PID unchanged)
    rc, pid0_after, _ = await run_in_unit(
        unit0, f"systemctl show {service0} --property=MainPID --value"
    )
    assert rc == 0, "Failed to get unit0 MainPID after unit1 restart"
    pid0_after = (pid0_after or "").strip()
    assert pid0_after == pid0_before, "unit0 PID should NOT have changed when unit1 restarted"

    # Both services should still be responding
    rc, _, _ = await run_in_unit(
        unit0, f"curl -sf http://127.0.0.1:{port0}/metrics", assert_on_failure=True
    )
    rc, _, _ = await run_in_unit(
        unit1, f"curl -sf http://127.0.0.1:{port1}/metrics", assert_on_failure=True
    )

    # Verify unit1's old process is no longer running
    rc, _, _ = await run_in_unit(unit1, f"ps -p {pid1_before} >/dev/null 2>&1")
    assert rc != 0, f"Old unit1 process {pid1_before} should not be running after restart"

    # Verify unit0's process is still running
    rc, _, _ = await run_in_unit(unit0, f"ps -p {pid0_after} >/dev/null 2>&1")
    assert rc == 0, f"unit0 process {pid0_after} should still be running"

    # Check systemd logs for no left-over warnings on unit1
    rc, journal_output, _ = await run_in_unit(
        unit1,
        f"sudo journalctl -u {service1} --since '2 minutes ago' | "
        f"grep -i 'left-over process' || true",
    )
    leftover_warnings = (journal_output or "").strip()
    assert (
        not leftover_warnings
    ), f"Found 'left-over process' warnings in unit1 logs:\n{leftover_warnings}"

