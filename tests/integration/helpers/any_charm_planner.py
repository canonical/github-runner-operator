# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# This Python script is designed to be loaded into any-charm. Some lint checks do not apply
# pylint: disable=import-error,consider-using-with,duplicate-code

"""This code snippet is used to be loaded into any-charm which is used for integration tests."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from any_charm_base import AnyCharmBase


class AnyCharm(AnyCharmBase):
    """Execute a HTTP server to mock GitHub runner Planner charm."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret = None

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(
            self.on["provide-github-runner-planner-v0"].relation_changed,
            self._on_planner_relation_changed,
        )

    def _on_install(self, _):
        threading.Thread(
            target=run_server,
            args=(str(self.model.get_binding("juju-info").network.bind_address),),
            daemon=True,
        ).start()

    def _on_planner_relation_changed(self, event):
        """Handle relation changed event for planner interface."""
        # Provide mock planner relation data
        event.relation.data[self.unit]["endpoint"] = str(
            self.model.get_binding("juju-info").network.bind_address
        )
        event.relation.data[self.unit]["token"] = "{planner_token_secret}"


class MockPlannerHandler(BaseHTTPRequestHandler):
    """Handler for mock planner HTTP server."""

    def __init__(self, *args, **kwargs):
        """Initialize the mock planner handler.

        Args:
            args: Positional arguments.
            kwargs: Keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.last_payload = None

    # Ignore function name lint as do_POST is the name used by BaseHTTPRequestHandler
    def do_POST(self):  # noqa: N802
        """Handle all POST request."""
        if self.path.startswith("/api/v1/auth/token/"):
            content_length = int(self.headers["Content-Length"])
            self.last_payload = self.rfile.read(content_length)

            self.send_response(200)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    # Ignore function name lint as do_GET is the name used by BaseHTTPRequestHandler
    def do_GET(self):  # noqa: N802
        """Handle all GET request."""
        if self.last_payload is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.last_payload)


def run_server(address: str):
    """Run the mock planner HTTP server."""
    server = HTTPServer(server_address=(address, 80), RequestHandlerClass=MockPlannerHandler)
    server.serve_forever()
