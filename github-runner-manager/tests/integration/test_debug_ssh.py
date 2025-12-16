# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for tmate ssh connection."""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Generator, Iterator

import docker
import pytest
import yaml
from docker.models.containers import Container
from github.Branch import Branch
from github.Repository import Repository

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
    except Exception:
        pass
    return ""


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
def tmate_keys(tmp_path_factory) -> Generator[TmateKeys, None, None]:
    """Generate SSH keypairs under `tmp_path/keys` and compute SHA256 fingerprints.

    Yields a dict with `keys_dir`, `rsa_key`, `ed_key`, `rsa_fingerprint`, and
    `ed25519_fingerprint`.
    """
    keys_dir = tmp_path_factory.mktemp("tmate-ssh-keys")
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

    rsa_fingerprint = compute_ssh_fingerprint(rsa_key_path.with_suffix(".pub"))
    ed25519_fingerprint = compute_ssh_fingerprint(ed_key_path.with_suffix(".pub"))

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

    # Run container detached and publish port 22 to a 10022 host port,
    # mount the generated keys at /keys so the server can use them.
    container: Container = client.containers.run(
        tmate_image,
        command=["-h", "0.0.0.0", "-p", "10022", "-k", "/keys/"],
        environment={"SSH_KEYS_PATH": "/keys"},
        detach=True,
        name=name,
        ports={"10022/tcp": "10022/tcp"},
        volumes={tmate_keys.keys_dir: {"bind": "/keys", "mode": "ro"}},
        user="root",
        cap_add=["SYS_ADMIN"],
        remove=False,
    )
    container.reload()

    host = "127.0.0.1"
    port = get_container_mapped_port(container, "10022/tcp")
    if port is None:
        try:
            container.remove(force=True)
        except Exception as exc:
            logger.error("Failed to remove tmate container: %s", exc)
            pass
        pytest.fail(f"Failed to get tmate container SSH port: {port}")

    yield TmateServer(
        host=host,
        port=port,
        rsa_fingerprint=tmate_keys.rsa_fingerprint,
        ed25519_fingerprint=tmate_keys.ed25519_fingerprint,
    )

    try:
        container.remove(force=True)
    except Exception as exc:
        logger.error("Failed to remove tmate container: %s", exc)


@pytest.fixture(scope="module")
def application_with_tmate_ssh_server(
    tmp_path: Path,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig | None,
    test_config: TestConfig,
    proxy_config: ProxyConfig | None,
    tmate_ssh_server: TmateServer,
) -> Iterator[RunningApplication]:
    """Start application with external contributor checks enabled (disabled access).

    Args:
        tmp_path: Pytest fixture providing temporary directory.
        github_config: GitHub configuration object.
        openstack_config: OpenStack configuration object or None.
        test_config: Test-specific configuration for unique identification.
        proxy_config: Proxy configuration object or None.

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
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    logger.info(
        "Starting application with SSH debug configuration (test_id: %s)",
        test_config.test_id,
    )
    metrics_log_path = tmp_path / "github-runner-metrics.log"
    log_file_path = test_config.debug_log_dir / f"application-{test_config.test_id}.log"
    app = RunningApplication.create(
        config_path, metrics_log_path=metrics_log_path, log_file_path=log_file_path
    )

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
    workflow_run = get_workflow_dispatch_run(
        workflow=workflow, ref=github_branch, dispatch_time=dispatch_time
    )
    assert wait_for_workflow_completion(
        workflow_run, timeout=900
    ), "Workflow did not complete successfully or timed out."
    logs = get_job_logs(workflow_run)

    assert tmate_ssh_server.host in logs, "Tmate ssh server IP not found in action logs."
    assert (
        tmate_ssh_server.port in logs
    ), "Tmate ssh server connection port not found in action logs."
