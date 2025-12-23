# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test infrastructure for managing running application instances."""

import logging
import multiprocessing
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml

logger = logging.getLogger(__name__)


def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    """Wait for a server to become responsive.

    Args:
        host: The host to connect to.
        port: The port to connect to.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if the server became responsive, False otherwise.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"http://{host}:{port}/health", timeout=1, allow_redirects=False
            )
            if response.status_code in (200, 204, 404):  # Server is responding
                return True
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.5)
    return False


def _start_cli_server(
    config_file_path: Path, port: int, host: str = "127.0.0.1", log_file_path: Path | None = None
) -> None:
    """Start the CLI server in a separate process.

    Args:
        config_file_path: Path to the configuration file.
        port: Port to listen on.
        host: Host to listen on.
        log_file_path: Path to the log file for stdout/stderr. If None, uses stdout/stderr.
    """
    args = [
        "/usr/bin/sudo",
        "-E",
        sys.executable,
        "-m",
        "github_runner_manager.cli",
        "--config-file",
        str(config_file_path),
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "DEBUG",
    ]

    logger.info("Starting CLI server with command: %s", " ".join(args))

    # Redirect output to log file or stdout/stderr
    if log_file_path:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_file_path, "w", encoding="utf-8")
        stdout_target = log_file
        stderr_target = log_file
        logger.info("CLI output will be written to %s", log_file_path)
    else:
        log_file = None
        stdout_target = sys.stdout
        stderr_target = sys.stderr

    # Start process and wait for it to exit
    process = subprocess.Popen(
        args,
        stdout=stdout_target,
        stderr=stderr_target,
    )

    # Block until the subprocess exits (either naturally or when terminated)
    return_code = process.wait()

    # Close log file if we opened one
    if log_file:
        log_file.close()

    logger.info("CLI server exited with code %d", return_code)


@dataclass
class RunningApplication:
    """Information about a running application instance.

    This class manages the lifecycle of a github-runner-manager application
    instance running in a separate process for integration testing.

    Attributes:
        base_url: The base URL (e.g., http://127.0.0.1:8080).
        config: The configuration dictionary.
        process: The multiprocessing.Process running the application.
        port: The port the application is listening on.
        host: The host the application is listening on.
        config_file_path: Path to the configuration file used.
    """

    process: multiprocessing.Process
    port: int
    host: str
    config_file_path: Path

    @property
    def base_url(self) -> str:
        """Get the base URL of the application.

        Returns:
            The base URL (e.g., http://127.0.0.1:8080).
        """
        return f"http://{self.host}:{self.port}"

    @property
    def config(self) -> dict[str, Any]:
        """Get the configuration used to start the application.

        Returns:
            The configuration dictionary.
        """
        return yaml.safe_load(self.config_file_path.read_text(encoding="utf-8"))

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Make a GET request to the application.

        Args:
            path: The path to request (e.g., /health).
            kwargs: Additional arguments to pass to requests.get.

        Returns:
            The response object.
        """
        url = f"{self.base_url}{path}"
        return requests.get(url, **kwargs)

    def is_alive(self) -> bool:
        """Check if the application process is still alive.

        Returns:
            True if the process is alive, False otherwise.
        """
        return self.process.is_alive()

    @classmethod
    def create(
        cls,
        config_file_path: Path,
        host: str = "127.0.0.1",
        port: int = 8080,
        metrics_log_path: Path | None = None,
        log_file_path: Path | None = None,
    ) -> "RunningApplication":
        """Create and start a new application instance.

        Args:
            config_file_path: Path to the configuration file.
            host: Host to listen on. Defaults to 127.0.0.1.
            port: Port to listen on. If None, an available port is automatically selected.
            metrics_log_path: Path to the metrics log file. If provided, sets METRICS_LOG_PATH
                environment variable for the application process.
            log_file_path: Path to the application log file. If None, logs to stderr.

        Returns:
            A RunningApplication instance with the application running.

        Raises:
            RuntimeError: If the application fails to start.
        """
        # Set metrics log path if provided
        if metrics_log_path:
            os.environ["METRICS_LOG_PATH"] = str(metrics_log_path)

        # Start the server process
        process = multiprocessing.Process(
            target=_start_cli_server,
            args=(config_file_path, port, host, log_file_path),
        )
        process.start()

        # Wait for the server to become ready
        server_ready = wait_for_server(host, port, timeout=10.0)

        if not server_ready:
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
            raise RuntimeError(
                f"Application failed to start within the expected time on {host}:{port}"
            )

        return cls(
            process=process,
            port=port,
            host=host,
            config_file_path=config_file_path,
        )

    def stop(self) -> None:
        """Stop the application process."""
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
