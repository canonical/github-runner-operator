#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for collecting metrics related to the reconciliation process."""

import secrets
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from github.Branch import Branch
from github.Repository import Repository
from juju.action import Action
from juju.application import Application
from juju.controller import Controller
from juju.model import Model
from openstack.connection import Connection

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, CUSTOM_PRE_JOB_SCRIPT_CONFIG_NAME
from tests.integration.helpers.common import (
    DISPATCH_TEST_WORKFLOW_FILENAME,
    DISPATCH_WAIT_TEST_WORKFLOW_FILENAME,
    dispatch_workflow,
    get_job_logs,
    wait_for,
    wait_for_reconcile,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, setup_repo_policy


@pytest_asyncio.fixture(scope="module", name="k8s_controller")
async def k8s_controller_fixture() -> AsyncGenerator[Controller, None]:
    """The k8s controller.

    See scripts/setup-integration-tests.sh.
    """
    controller = Controller()
    await controller.connect_controller("microk8s")
    yield controller
    await controller.disconnect()


@pytest_asyncio.fixture(scope="module", name="k8s_model")
async def k8s_model_fixture(k8s_controller: Controller) -> AsyncGenerator[Model, None]:
    """The machine model for jenkins agent machine charm."""
    k8s_model_name = f"k8s-{secrets.token_hex(2)}"
    model = await k8s_controller.add_model(k8s_model_name)
    await model.connect(f"localhost:admin/{model.name}")
    yield model
    await k8s_controller.destroy_models(
        model.name, destroy_storage=True, force=True, max_wait=10 * 60
    )
    await model.disconnect()


@pytest_asyncio.fixture(scope="module", name="prometheus_app")
async def prometheus_app_fixture(k8s_model: Model):
    """Deploy prometheus charm."""
    prometheus_app: Application = await k8s_model.deploy("prometheus-k8s", channel="1/stable")
    return prometheus_app


async def test_prometheus_metrics(
    model: Model, k8s_model: Model, app_openstack_runner: Application, prometheus_app: Application
):
    """
    arrange: given a prometheus charm application.
    act: when GitHub runner is integrated.
    assert: the datasource is registered and basic metrics are available.
    """
    offer = await k8s_model.create_offer(f"{prometheus_app.name}:metrics-endpoint", "metrics")
    await model.integrate(
        app_openstack_runner.name, f"microk8s:admin/{k8s_model.name}.{offer.name}"
    )
    await k8s_model.wait_for_idle(apps=[prometheus_app.name], timeout=300)
    await model.wait_for_idle(apps=[app_openstack_runner.name], timeout=300)

    assert False
