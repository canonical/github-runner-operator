# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Lightweight planner stub for integration tests.

Provides flavor info and pressure endpoints expected by PlannerClient:
- GET /api/v1/flavors/<name>/pressure
- GET /api/v1/flavors/<name>/pressure?stream=true (NDJSON)
- POST /control/pressure (test control endpoint for dynamic pressure updates)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass

import requests
from flask import Flask, Response, request

from tests.integration.application import wait_for_server

logger = logging.getLogger(__name__)


@dataclass
class PlannerStubConfig:
    """Configuration for the planner stub server."""

    host: str = "127.0.0.1"
    port: int = 8081
    token: str = "stub-token"
    flavor_name: str = "small"
    initial_pressure: int = 1


def _make_app(config: PlannerStubConfig, state: dict[str, int]) -> Flask:
    """Create a Flask app configured as a planner stub server.

    Args:
        config: Configuration for the planner stub.
        state: Shared mutable dict holding {"pressure": <int>}.

    Returns:
        Flask: Configured Flask app instance.
    """
    app = Flask(__name__)

    @app.get("/health")
    def health() -> Response:
        """Health endpoint for readiness checks."""
        return Response(status=204)

    @app.get(f"/api/v1/flavors/{config.flavor_name}/pressure")
    def get_pressure() -> Response:
        """Return the current pressure as a snapshot or NDJSON stream."""
        if request.args.get("stream") != "true":
            return Response(
                json.dumps({"pressure": state["pressure"]}), mimetype="application/json"
            )

        def stream():
            """Yield NDJSON pressure lines indefinitely.

            Yields:
                NDJSON-encoded bytes with the current pressure.
            """
            while True:
                p = state["pressure"]
                logger.info("Stream: yielding pressure=%d", p)
                yield (json.dumps({config.flavor_name: p}) + "\n").encode("utf-8")
                time.sleep(10)

        return Response(stream(), mimetype="application/x-ndjson")

    @app.post("/control/pressure")
    def control_pressure() -> Response:
        """Update the pressure served by all subsequent requests."""
        payload = request.get_json(force=True)
        pressure = int(payload.get("pressure", 0))
        state["pressure"] = pressure
        logger.info("Control: pressure set to %d", pressure)
        return Response(json.dumps({"pressure": pressure}), mimetype="application/json")

    return app


class PlannerStub:
    """Lifecycle manager for the planner stub HTTP server."""

    def __init__(self, config: PlannerStubConfig | None = None) -> None:
        """Initialize the planner stub manager.

        Args:
            config: Optional configuration for host, port, token, flavor name,
                and initial pressure. If not provided, defaults from
                `PlannerStubConfig` are used.
        """
        self._config = config or PlannerStubConfig()
        self._thread: threading.Thread | None = None
        self._port = self._config.port

    @property
    def base_url(self) -> str:
        """Return the base URL of the running stub."""
        return f"http://{self._config.host}:{self._port}"

    @property
    def token(self) -> str:
        """Return the expected bearer token for requests to the stub."""
        return self._config.token

    def start(self) -> None:
        """Start the planner stub server in a daemon thread."""
        state = {"pressure": self._config.initial_pressure}
        app = _make_app(self._config, state)
        self._thread = threading.Thread(
            target=app.run,
            kwargs={
                "host": self._config.host,
                "port": self._port,
                "debug": False,
                "use_reloader": False,
            },
            daemon=True,
        )
        self._thread.start()
        if not wait_for_server(self._config.host, self._port, timeout=5.0):
            raise TimeoutError(
                f"PlannerStub server did not become ready on"
                f" {self._config.host}:{self._port} within 5 seconds"
            )

    def stop(self) -> None:
        """Stop the planner stub server if it is running.

        Since Flask's dev server has no clean shutdown API and the thread is a
        daemon, it will be cleaned up automatically when the process exits.
        """
        self._thread = None

    def set_pressure(self, value: int) -> None:
        """Update the pressure served by the stub server.

        POSTs to the stub's own ``/control/pressure`` endpoint so the change
        is immediately reflected in both snapshot and streaming responses.

        Args:
            value: The new pressure value to serve.
        """
        response = requests.post(
            f"{self.base_url}/control/pressure",
            json={"pressure": value},
            timeout=5,
        )
        response.raise_for_status()
