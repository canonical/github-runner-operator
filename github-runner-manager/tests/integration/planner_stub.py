# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Lightweight planner stub for integration tests.

Provides flavor info and pressure endpoints expected by PlannerClient:
- GET /api/v1/flavors/<name>
- GET /api/v1/flavors/<name>/pressure
- GET /api/v1/flavors/<name>/pressure?stream=true (NDJSON)
"""

from __future__ import annotations

import json
import multiprocessing
import time
from dataclasses import dataclass
from typing import Iterable

import requests
from flask import Flask, Response, request


@dataclass
class PlannerStubConfig:
    """Configuration for the planner stub server."""

    host: str = "127.0.0.1"
    port: int = 8081
    token: str = "stub-token"
    flavor_name: str = "small"
    minimum_pressure: int = 0
    stream_sequence: tuple[float, ...] = (1.0, 1.0, 1.0)
    stream_interval_seconds: float = 10


def _make_app(config: PlannerStubConfig) -> Flask:
    """Create a Flask app configured as a planner stub server.

    Args:
        config: Configuration for the planner stub.

    Returns:
        Flask: Configured Flask app instance.
    """
    app = Flask(__name__)

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
        """Return the latest pressure snapshot for the flavor.

        Returns:
            Response: JSON body with a single `pressure` float value.
        """
        payload = {"pressure": float(config.stream_sequence[-1])}
        return Response(json.dumps(payload), mimetype="application/json")

    @app.get(f"/api/v1/flavors/{config.flavor_name}/pressure")
    def stream_pressure() -> Response:  # type: ignore[no-redef]
        """Return an NDJSON stream of pressure updates when requested.

        If the query parameter `stream=true` is present, an NDJSON stream of
        pressure updates is returned; otherwise, a single pressure snapshot is
        returned.

        Returns:
            Response: NDJSON stream or a single JSON snapshot.
        """
        if request.args.get("stream") != "true":
            return get_pressure()

        def _gen() -> Iterable[bytes]:
            """Yield NDJSON-encoded pressure values on a schedule.

            Yields:
                Iterable[bytes]: Sequence of NDJSON lines as byte strings.
            """
            # Emit a few cycles deterministically, then stop.
            cycles = 5
            for _ in range(cycles):
                for p in config.stream_sequence:
                    line = json.dumps({"pressure": float(p)}) + "\n"
                    yield line.encode("utf-8")
                    time.sleep(config.stream_interval_seconds)

        return Response(_gen(), mimetype="application/x-ndjson")

    return app


class PlannerStub:
    """Lifecycle manager for the planner stub HTTP server."""

    def __init__(self, config: PlannerStubConfig | None = None) -> None:
        """Initialize the planner stub manager.

        Args:
            config: Optional configuration for host, port, token, flavor name,
                minimum pressure, and stream behavior. If not provided,
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
