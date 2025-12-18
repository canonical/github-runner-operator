# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for tmate ssh connection."""

import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Generator, Iterator

import docker
import docker.errors
import openstack
import pytest
import yaml
from docker.models.containers import Container
from github.Branch import Branch
from github.Repository import Repository
from openstack.compute.v2.server import Server as OpenstackServer

from .application import RunningApplication
from .factories import (
    GitHubConfig,
    OpenStackConfig,
    ProxyConfig,
    SSHDebugConfiguration,
    TestConfig,
    create_default_config,
)
from .github_helpers import (
    dispatch_workflow,
    get_job_logs,
    get_workflow_dispatch_run,
    wait_for_workflow_completion,
)

logger = logging.getLogger(__name__)

SSH_DEBUG_WORKFLOW_FILE_NAME = "workflow_dispatch_ssh_debug.yaml"
TMATE_SSH_PORT = 10022


@dataclass
class TmateKeys:
    """Structured representation of generated tmate SSH key artifacts.

    Attributes:
        keys_dir: Path to directory containing key files.
        rsa_fingerprint: SHA256 fingerprint for the RSA public key.
        ed25519_fingerprint: SHA256 fingerprint for the Ed25519 public key.
    """

    keys_dir: str
    rsa_fingerprint: str
    ed25519_fingerprint: str


@dataclass
class TmateServer:
    """Structured representation of a running tmate SSH server.

    Attributes:
        host: The SSH server host.
        port: The mapped SSH port on the host.
        rsa_fingerprint: SHA256 fingerprint for the RSA public key.
        ed25519_fingerprint: SHA256 fingerprint for the Ed25519 public key.
    """

    host: str
    port: int
    rsa_fingerprint: str
    ed25519_fingerprint: str


def wait_for_runner(
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    timeout: int = 300,
    interval: int = 5,
) -> tuple[OpenstackServer, str] | tuple[None, None]:
    """Wait for an OpenStack runner to be created and return it with its IP.

    Args:
        openstack_connection: OpenStack connection object.
        test_config: Test configuration with VM prefix.
        timeout: Maximum time to wait in seconds.
        interval: Time between checks in seconds.

    Returns:
        Tuple of (runner, ip) if found, or (None, None) if not found within timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        servers = [
            server
            for server in openstack_connection.list_servers()
            if server.name.startswith(test_config.vm_prefix)
        ]
        if servers:
            runner = servers[0]
            logger.info("Found runner: %s", runner.name)

            # Get runner IP
            ip = None
            for network_addresses in runner.addresses.values():
                for address in network_addresses:
                    ip = address["addr"]
                    break
                if ip:
                    break

            if ip:
                return runner, ip

        time.sleep(interval)

    return None, None


def wait_for_ssh(runner_ip: str, port: int = 22, timeout: int = 120, interval: int = 2) -> bool:
    """Wait for SSH port to become available on the runner.

    Args:
        runner_ip: IP address of the runner.
        port: SSH port to check (default: 22).
        timeout: Maximum time to wait in seconds.
        interval: Time between connection attempts in seconds.

    Returns:
        True if SSH is available, False if timeout reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((runner_ip, port), timeout=5):
                logger.info("SSH port %d is now available on %s", port, runner_ip)
                return True
        except (socket.timeout, socket.error, OSError):
            time.sleep(interval)

    logger.error("SSH port %d never became available on %s", port, runner_ip)
    return False


def setup_reverse_ssh_tunnel(
    runner: OpenstackServer,
    runner_ip: str,
    tmate_ssh_server: TmateServer,
) -> bool:
    """Setup reverse SSH tunnel and DNAT rules for tmate server access.

    Args:
        runner: OpenStack server object for the runner.
        runner_ip: IP address of the runner.
        tmate_ssh_server: Tmate SSH server configuration.

    Returns:
        True if tunnel and DNAT were successfully established, False otherwise.
    """
    key_name = runner.name
    key_path = Path.home() / ".ssh" / f"{key_name}.key"

    logger.info("Waiting for SSH on runner %s at %s...", runner.name, runner_ip)
    if not wait_for_ssh(runner_ip):
        logger.error("SSH never became available on runner %s", runner_ip)
        return False

    # Setup DNAT rule to redirect tmate server traffic to localhost tunnel endpoint
    dnat_cmd = (
        f"sudo iptables -t nat -A OUTPUT -p tcp "
        f"-d {tmate_ssh_server.host} --dport {tmate_ssh_server.port} "
        f"-j DNAT --to-destination 127.0.0.1:3129"
    )

    logger.info("Configuring DNAT rule on runner")
    try:
        subprocess.run(
            [
                "/usr/bin/ssh",
                "-i",
                str(key_path),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"ubuntu@{runner_ip}",
                dnat_cmd,
            ],
            check=True,
            timeout=30,
            capture_output=True,
            text=True,
        )
        logger.info("DNAT rule configured on runner")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to setup DNAT rule: %s, stderr: %s", e, e.stderr)
        return False

    # Setup reverse SSH tunnel: runner's localhost:3129 -> test host's tmate server
    ssh_cmd = [
        "/usr/bin/ssh",
        "-fNT",
        "-R",
        f"3129:{tmate_ssh_server.host}:{tmate_ssh_server.port}",
        "-i",
        str(key_path),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ServerAliveInterval=60",
        "-o",
        "ExitOnForwardFailure=yes",
        f"ubuntu@{runner_ip}",
    ]
    logger.info("Setting up reverse SSH tunnel: %s", " ".join(ssh_cmd))
    try:
        result = subprocess.run(ssh_cmd, check=True, timeout=30, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Reverse SSH tunnel established")
            return True
        else:
            logger.error("SSH tunnel command failed: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("SSH tunnel command timed out")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("Failed to setup reverse SSH tunnel: %s, stderr: %s", e, e.stderr)
        return False


def compute_ssh_fingerprint(pub_path: str) -> str:
    """Return SHA256 fingerprint for a public key using `/usr/bin/ssh-keygen`.

    Returns the fingerprint string like `SHA256:...` or an empty string on failure.
    """
    try:
        proc = subprocess.run(
            ["/usr/bin/ssh-keygen", "-l", "-E", "SHA256", "-f", str(pub_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        out = proc.stdout.strip()
        parts = out.split()
        if len(parts) >= 2 and parts[1].startswith("SHA256:"):
            return parts[1]
    except OSError as exc:
        logger.error("Failed to compute SSH fingerprint for %s: %s", pub_path, exc)
    return ""


def get_container_mapped_port(
    container: Container,
    container_port: str = "22/tcp",
    attempts: int = 30,
    interval: float = 0.5,
) -> int | None:
    """Return the mapped host port for `container_port` or None if not found.

    Reloads container attributes between attempts.
    """
    for _ in range(attempts):
        container.reload()
        ports_info = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        mapping = ports_info.get(container_port)
        if mapping and isinstance(mapping, list) and mapping[0].get("HostPort"):
            try:
                return int(mapping[0]["HostPort"])
            except (ValueError, TypeError):
                return None
        sleep(interval)
    return None


@pytest.fixture(scope="module")
def tmate_keys(tmp_test_dir: Path) -> Generator[TmateKeys, None, None]:
    """Generate SSH keypairs under `tmp_path/keys` and compute SHA256 fingerprints.

    Yields a dict with `keys_dir`, `rsa_key`, `ed_key`, `rsa_fingerprint`, and
    `ed25519_fingerprint`.
    """
    keys_dir = tmp_test_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    rsa_key_path = keys_dir / "ssh_host_rsa_key"
    ed_key_path = keys_dir / "ssh_host_ed25519_key"

    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",  # quiet
            "-t",  # type
            "rsa",
            "-b",  # bits
            "2048",
            "-f",  # file path
            str(rsa_key_path),
            "-N",  # new passphrase
            "",
        ],
        check=True,
    )
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-f",
            str(ed_key_path),
            "-N",
            "",
        ],
        check=True,
    )

    rsa_fingerprint = compute_ssh_fingerprint(str(rsa_key_path.with_suffix(".pub")))
    ed25519_fingerprint = compute_ssh_fingerprint(str(ed_key_path.with_suffix(".pub")))

    yield TmateKeys(
        keys_dir=str(keys_dir),
        rsa_fingerprint=rsa_fingerprint,
        ed25519_fingerprint=ed25519_fingerprint,
    )


@pytest.fixture(scope="module")
def tmate_image(pytestconfig):
    """Return the tmate image to use for SSH server testing."""
    return pytestconfig.getoption("--tmate-image")


@pytest.fixture(scope="module")
def tmate_ssh_server(
    tmate_keys: TmateKeys, test_config: TestConfig, tmate_image: str
) -> Generator[TmateServer, None, None]:
    """Start a tmate SSH server in Docker and yield connection info.

    Uses the image from the tmate_image fixture. Yields a TmateServer
    with connection details and fingerprints.
    """
    name = f"test-tmate-{test_config.test_id}"
    client = docker.from_env()

    host = "127.0.0.1"
    # Run container detached and publish port 22 to host port (defined by TMATE_SSH_PORT constant),
    # mount the generated keys at /keys so the server can use them.
    container: Container = client.containers.run(
        tmate_image,
        command=["-h", host, "-p", str(TMATE_SSH_PORT), "-k", "/keys/"],
        environment={"SSH_KEYS_PATH": "/keys"},
        detach=True,
        name=name,
        ports={f"{TMATE_SSH_PORT}/tcp": f"{TMATE_SSH_PORT}/tcp"},
        volumes={tmate_keys.keys_dir: {"bind": "/keys", "mode": "ro"}},
        user="root",
        cap_add=["SYS_ADMIN"],
        remove=False,
    )
    container.reload()

    port = get_container_mapped_port(container, f"{TMATE_SSH_PORT}/tcp")
    if port is None:
        try:
            container.remove(force=True)
        except docker.errors.DockerException as exc:
            logger.error("Failed to remove tmate container: %s", exc)
        pytest.fail(f"Failed to get tmate container SSH port: {port}")

    yield TmateServer(
        host=host,
        port=port,
        rsa_fingerprint=tmate_keys.rsa_fingerprint,
        ed25519_fingerprint=tmate_keys.ed25519_fingerprint,
    )

    try:
        log_path = test_config.debug_log_dir / "tmate-server.log"
        log_path.write_text(
            container.logs(stdout=True, stderr=True, stream=False).decode("utf-8"),
            encoding="utf-8",
        )
        container.remove(force=True)
    except Exception as exc:
        logger.error("Failed to remove tmate container: %s", exc)


@pytest.fixture(scope="module")
def application_with_tmate_ssh_server(
    tmp_test_dir: Path,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    openstack_connection: openstack.connection.Connection,
    test_config: TestConfig,
    proxy_config: ProxyConfig | None,
    tmate_ssh_server: TmateServer,
) -> Iterator[RunningApplication]:
    """Start application with tmate SSH server and reverse proxy for runner access.

    Args:
        tmp_test_dir: Pytest fixture providing temporary directory.
        github_config: GitHub configuration object.
        openstack_config: OpenStack configuration object or None.
        openstack_connection: OpenStack connection object or None.
        test_config: Test-specific configuration for unique identification.
        proxy_config: Proxy configuration object or None.
        tmate_ssh_server: Tmate SSH server fixture.

    Yields:
        A running application instance.
    """
    config = create_default_config(
        github_config=github_config,
        openstack_config=openstack_config,
        proxy_config=proxy_config,
        test_config=test_config,
        ssh_debug_connections=[
            SSHDebugConfiguration(
                host=tmate_ssh_server.host,
                port=tmate_ssh_server.port,
                rsa_fingerprint=tmate_ssh_server.rsa_fingerprint,
                ed25519_fingerprint=tmate_ssh_server.ed25519_fingerprint,
                use_runner_http_proxy=False,
                local_proxy_host="127.0.0.1",
                local_proxy_port=3129,
            )
        ],
    )
    config_path = tmp_test_dir / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    logger.info(
        "Starting application with SSH debug configuration (test_id: %s)",
        test_config.test_id,
    )
    metrics_log_path = tmp_test_dir / "github-runner-metrics.log"
    log_file_path = test_config.debug_log_dir / f"application-{test_config.test_id}.log"
    app = RunningApplication.create(
        config_path, metrics_log_path=metrics_log_path, log_file_path=log_file_path
    )

    # Wait for runner to be created and setup reverse SSH tunnel
    logger.info("Waiting for OpenStack runner to be created...")
    runner, ip = wait_for_runner(openstack_connection, test_config)

    if not runner or not ip:
        pytest.fail("Failed to find OpenStack runner within timeout")

    if not setup_reverse_ssh_tunnel(runner, ip, tmate_ssh_server):
        pytest.fail("Failed to setup reverse SSH tunnel to tmate server")

    yield app

    logger.info("Stopping application")
    app.stop()


@pytest.mark.usefixtures("application_with_tmate_ssh_server")
def test_tmate_ssh_connection(
    test_config: TestConfig,
    github_repository: Repository,
    github_branch: Branch,
    tmate_ssh_server: TmateServer,
):
    """Test that a tmate SSH connection can be established via the runner manager.

    Arrange: Application configured with tmate SSH server connection details.
    Act: Dispatch workflow that connects to the tmate SSH server.
    Assert: Workflow completes successfully and logs contain server connection details.

    Args:
        test_config: Test-specific configuration for unique identification.
        github_repository: Fixture providing the GitHub repository object.
        github_branch: Fixture providing the GitHub branch object.
        tmate_ssh_server: Fixture providing the tmate SSH server connection info.
    """
    dispatch_time = datetime.now(timezone.utc)
    workflow = dispatch_workflow(
        repository=github_repository,
        workflow_filename=SSH_DEBUG_WORKFLOW_FILE_NAME,
        ref=github_branch,
        inputs={"runner": test_config.labels[0]},
    )
    # Note: This workflow will timeout if SSH connection cannot be established.
    # The test expects the workflow to succeed, indicating successful SSH connection.
    workflow_run = get_workflow_dispatch_run(
        workflow=workflow, ref=github_branch, dispatch_time=dispatch_time
    )
    assert wait_for_workflow_completion(
        workflow_run, timeout=900
    ), "Workflow did not complete or timed out."

    # Verify workflow succeeded (SSH connection was established)
    assert workflow_run.conclusion == "success", (
        f"Workflow did not succeed. Conclusion: {workflow_run.conclusion}"
    )

    logs = get_job_logs(workflow_run)

    assert tmate_ssh_server.host in logs, "Tmate ssh server IP not found in action logs."
