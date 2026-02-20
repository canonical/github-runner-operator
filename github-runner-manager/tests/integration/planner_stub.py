# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Lightweight planner stub for integration tests.

Provides flavor info and pressure endpoints expected by PlannerClient:
- GET /api/v1/flavors/<name>
- GET /api/v1/flavors/<name>/pressure
- GET /api/v1/flavors/<name>/pressure?stream=true (NDJSON)
- POST /control/pressure (test control endpoint for dynamic pressure updates)
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from flask import Flask, Response, request

logger = logging.getLogger(__name__)


@dataclass
class PlannerStubConfig:
    """Configuration for the planner stub server."""

    host: str = "127.0.0.1"
    port: int = 8081
    token: str = "stub-token"
    flavor_name: str = "small"
    minimum_pressure: int = 0
    initial_pressure: float = 1.0


def _pressure_file_path(port: int) -> Path:
    """Return the path to the pressure state file for the given port.

    Port-namespaced to allow parallel test execution without conflicts.
    """
    return Path(f"/tmp/planner_stub_{port}_pressure.json")


def _read_pressure(pressure_path: Path, default: float) -> float:
    """Read the current pressure value from the state file.

    Args:
        pressure_path: Path to the JSON pressure state file.
        default: Value to return if the file is missing or malformed.

    Returns:
        The pressure value from the file, or ``default`` on error.
    """
    try:
        data = json.loads(pressure_path.read_text(encoding="utf-8"))
        return float(data.get("pressure", default))
    except (json.JSONDecodeError, OSError):
        return default


def _pressure_stream_gen(pressure_path: Path, default: float) -> Iterable[bytes]:
    """Yield NDJSON-encoded pressure values indefinitely, re-reading the file each time.

    Yields one line every 10 seconds so that calls to ``/control/pressure`` are
    reflected in streaming consumers without restarting the server.

    Args:
        pressure_path: Path to the JSON pressure state file.
        default: Pressure value to use when the file is missing or malformed.

    Yields:
        Iterable[bytes]: NDJSON lines as byte strings.
    """
    while True:
        p = _read_pressure(pressure_path, default)
        logger.info("Stream: yielding pressure=%.2f (path=%s)", p, pressure_path)
        yield (json.dumps({"pressure": p}) + "\n").encode("utf-8")
        time.sleep(10)


def _make_app(config: PlannerStubConfig) -> Flask:
    """Create a Flask app configured as a planner stub server.

    Writes the initial pressure to a temp file so pressure persists across
    requests and can be updated dynamically via ``POST /control/pressure``.

    Args:
        config: Configuration for the planner stub.

    Returns:
        Flask: Configured Flask app instance.
    """
    app = Flask(__name__)
    pressure_path = _pressure_file_path(config.port)
    pressure_path.write_text(
        json.dumps({"pressure": config.initial_pressure}), encoding="utf-8"
    )

    @app.get("/health")
    def health() -> Response:
        """Health endpoint for readiness checks.

        Returns:
            Response: Empty 204 response indicating the server is ready.
        """
        return Response(status=204)

    @app.get(f"/api/v1/flavors/{config.flavor_name}")
    def get_flavor() -> Response:
        """Return flavor metadata for the configured flavor.

        Returns:
            Response: JSON body with `name`, `labels`, and `minimum_pressure`.
        """
        payload = {
            "name": config.flavor_name,
            "labels": [config.flavor_name],
            "minimum_pressure": config.minimum_pressure,
        }
        return Response(json.dumps(payload), mimetype="application/json")

    @app.get(f"/api/v1/flavors/{config.flavor_name}/pressure")
    def get_pressure() -> Response:
        """Return the current pressure as a snapshot or NDJSON stream.

        When ``stream=true`` is present in the query string, an NDJSON stream
        is returned that re-reads the pressure file on every iteration.
        Otherwise, a single JSON snapshot is returned.

        Returns:
            Response: JSON snapshot or infinite NDJSON stream.
        """
        if request.args.get("stream") != "true":
            p = _read_pressure(pressure_path, config.initial_pressure)
            return Response(json.dumps({"pressure": p}), mimetype="application/json")
        return Response(
            _pressure_stream_gen(pressure_path, config.initial_pressure),
            mimetype="application/x-ndjson",
        )

    @app.post("/control/pressure")
    def control_pressure() -> Response:
        """Update the pressure served by all subsequent requests.

        Writes the new value to the pressure file so both snapshot and
        streaming endpoints pick it up without a server restart.

        Returns:
            Response: JSON body with the newly set `pressure` value.
        """
        payload = request.get_json(force=True)
        pressure = float(payload.get("pressure", 0))
        pressure_path.write_text(json.dumps({"pressure": pressure}), encoding="utf-8")
        logger.info("Control: pressure set to %.2f (path=%s)", pressure, pressure_path)
        return Response(json.dumps({"pressure": pressure}), mimetype="application/json")

    return app


class PlannerStub:
    """Lifecycle manager for the planner stub HTTP server."""

    def __init__(self, config: PlannerStubConfig | None = None) -> None:
        """Initialize the planner stub manager.

        Args:
            config: Optional configuration for host, port, token, flavor name,
                minimum pressure, and initial pressure. If not provided,
                defaults from `PlannerStubConfig` are used.
        """
        self._config = config or PlannerStubConfig()
        self._process: multiprocessing.Process | None = None
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
        """Start the planner stub server in a separate process."""
        app = _make_app(self._config)
        self._process = multiprocessing.Process(
            target=app.run,
            kwargs={
                "host": self._config.host,
                "port": self._port,
                "debug": False,
                "use_reloader": False,
            },
            daemon=True,
        )
        self._process.start()
        # Wait for server to be ready via /health endpoint
        ready_url = f"http://{self._config.host}:{self._port}/health"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                resp = requests.get(ready_url, timeout=0.5)
                if resp.status_code in (200, 204):
                    break
            except requests.RequestException:
                pass
            time.sleep(0.1)

    def stop(self) -> None:
        """Stop the planner stub server if it is running."""
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.kill()
                self._process.join()

    def set_pressure(self, value: float) -> None:
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
