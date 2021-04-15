#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

import logging
import subprocess

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from runner import Runner

logger = logging.getLogger(__name__)


class GithubRunnerOperator(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.register_action, self._on_register_action)
        self._stored.set_default(registered=False)
        self._runner = Runner()

    def _on_install(self, _):
        self.unit.status = MaintenanceStatus("Installing runner")
        self._runner.download()
        self._runner.setup_env()
        self.unit.status = BlockedStatus("Waiting for registration")

    def _on_register_action(self, event):
        if self._stored.registered:
            event.set_results({"status": "Registration aborted, already registered"})
            logger.error("Can not re-register, unit is already registered")
            return
        self.unit.status = MaintenanceStatus("Registering runner")
        token = event.params["token"]
        url = event.params["url"]
        if not token:
            event.fail("No token provided")
            return
        if not url:
            event.fail("No url provided")
            return
        try:
            self._runner.register(url, token)
        except subprocess.CalledProcessError as e:
            logger.error("Register: failed")
            print(e)
            logger.error(f"Register: return code {e.returncode}")
            logger.error(f"Register: output {e.output}")
            raise
        event.set_results({"status": "runner registered"})
        self.unit.status = ActiveStatus("Active and registered")
        self._stored.registered = True


if __name__ == "__main__":
    main(GithubRunnerOperator)
