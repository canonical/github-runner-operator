# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factory functions for creating test data and configurations."""

import secrets
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _generate_test_id() -> str:
    """Generate a unique test identifier.

    Returns:
        A random 8-character alphanumeric string.
    """
    return "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))


@dataclass
class GitHubConfig:
    """GitHub configuration for tests.

    Attributes:
        token: GitHub personal access token.
        alt_token: Alternate GitHub personal access token for external contributor.
        path: GitHub path in <owner>/<repo> or <org> format.
    """

    token: str
    alt_token: str
    path: str


@dataclass
class OpenStackConfig:
    """OpenStack configuration for tests.

    Attributes:
        auth_url: OpenStack authentication URL.
        project: OpenStack project name.
        username: OpenStack username.
        password: OpenStack password.
        network: OpenStack network name.
        region_name: OpenStack region name.
        user_domain_name: OpenStack user domain name.
        project_domain_name: OpenStack project domain name.
        flavor: OpenStack flavor name for runner instances.
        image_id: OpenStack image ID for runner instances.
    """

    auth_url: str
    project: str
    username: str
    password: str
    network: str
    region_name: str = "RegionOne"
    user_domain_name: str = "Default"
    project_domain_name: str = "Default"
    flavor: str | None = None
    image_id: str | None = None


@dataclass
class ProxyConfig:
    """Proxy configuration for tests.

    Attributes:
        http_proxy: HTTP proxy URL.
        https_proxy: HTTPS proxy URL.
        no_proxy: Comma-separated list of hosts to exclude from proxy.
        openstack_http_proxy: HTTP proxy for OpenStack operations.
        openstack_https_proxy: HTTPS proxy for OpenStack operations.
        openstack_no_proxy: No proxy configuration for OpenStack operations.
    """

    http_proxy: str | None = None
    https_proxy: str | None = None
    no_proxy: str | None = None
    openstack_http_proxy: str | None = None
    openstack_https_proxy: str | None = None
    openstack_no_proxy: str | None = None


@dataclass
class TestConfig:
    """Test-specific configuration for parallel test execution.

    Attributes:
        debug_log_dir: Directory to store debug logs.
        test_id: Unique identifier for this test run.
        runner_name: Name prefix for the runner manager.
        labels: Extra labels to identify runners from this test.
        vm_prefix: Prefix for VM names to avoid conflicts.
    """

    debug_log_dir: Path = Path("/tmp/github-runner-manager-test-logs")
    test_id: str = field(default_factory=_generate_test_id)
    runner_name: str = field(init=False)
    labels: list[str] = field(init=False)
    vm_prefix: str = field(init=False)

    def __post_init__(self) -> None:
        """Initialize derived fields based on test_id."""
        self.runner_name = f"test-manager-{self.test_id}"
        self.labels = [f"test-{self.test_id}"]
        self.vm_prefix = f"test-runner-{self.test_id}"


@dataclass
class SSHDebugConfiguration:
    """SSH connection information for debug workflow.

    Attributes:
        host: The SSH relay server host IP address inside the VPN.
        port: The SSH relay server port.
        rsa_fingerprint: The host SSH server public RSA key fingerprint.
        ed25519_fingerprint: The host SSH server public ed25519 key fingerprint.
        use_runner_http_proxy: Whether to use runner proxy for the SSH connection.
        local_proxy_host: Local host to use for proxying.
        local_proxy_port: Local port to use for proxying.
    """

    host: str
    port: int = 0
    rsa_fingerprint: str = ""
    ed25519_fingerprint: str = ""
    use_runner_http_proxy: bool = False
    local_proxy_host: str = "127.0.0.1"
    local_proxy_port: int = 3129


@dataclass
class ReactiveConfig:
    """Reactive mode configuration for tests.

    Attributes:
        mq_uri: MongoDB connection URI.
        queue_name: Name of the queue to consume from.
        max_total_virtual_machines: Maximum number of runners allowed.
        images: List of images with their labels.
        flavors: List of flavors with their labels.
    """

    mq_uri: str
    queue_name: str
    max_total_virtual_machines: int = 1
    images: list[dict[str, Any]] | None = None
    flavors: list[dict[str, Any]] | None = None


def create_default_config(
    allow_external_contributor: bool = False,
    github_config: GitHubConfig | None = None,
    openstack_config: OpenStackConfig | None = None,
    proxy_config: ProxyConfig | None = None,
    ssh_debug_connections: list[SSHDebugConfiguration] | None = None,
    test_config: TestConfig | None = None,
    reactive_config: ReactiveConfig | None = None,
) -> dict[str, Any]:
    """Create a default test configuration dictionary.

    Args:
        allow_external_contributor: Whether to allow external contributors.
        github_config: GitHub configuration. Defaults to test values.
        openstack_config: OpenStack configuration. Defaults to test values.
        proxy_config: Proxy configuration. Defaults to no proxy.
        ssh_debug_connections: SSH debug connection configurations.
        test_config: Test-specific configuration for parallel execution.
            Defaults to new unique values.
        reactive_config: Reactive mode configuration. Defaults to None (non-reactive mode).

    Returns:
        Configuration dictionary for the application.
    """
    # Use defaults if not provided
    if github_config is None:
        github_config = GitHubConfig(
            token="ghp_test_token_1234567890abcdef",
            alt_token="ghp_test_alt_token_1234567890abcdef",
            path="test-org",
        )

    if openstack_config is None:
        openstack_config = OpenStackConfig(
            auth_url="http://openstack.example.com:5000/v3",
            project="test-project",
            username="test-user",
            password="test-password",
            network="test-network",
            region_name="RegionOne",
            flavor="small",
            image_id=None,
        )

    if test_config is None:
        test_config = TestConfig()

    # Parse GitHub path
    if "/" in github_config.path:
        owner, repo = github_config.path.split("/", 1)
        path_config = {"owner": owner, "repo": repo}
    else:
        path_config = {"org": github_config.path, "group": "default"}

    # Build proxy configuration
    runner_proxy = None
    if proxy_config and (proxy_config.http_proxy or proxy_config.https_proxy):
        runner_proxy = {
            "http": proxy_config.http_proxy,
            "https": proxy_config.https_proxy,
            "no_proxy": proxy_config.no_proxy,
        }

    openstack_proxy = None
    if proxy_config and (proxy_config.openstack_http_proxy or proxy_config.openstack_https_proxy):
        openstack_proxy = {
            "http": proxy_config.openstack_http_proxy,
            "https": proxy_config.openstack_https_proxy,
            "no_proxy": proxy_config.openstack_no_proxy,
        }

    return {
        "name": test_config.runner_name,
        "allow_external_contributor": allow_external_contributor,
        "extra_labels": test_config.labels,
        "github_config": {
            "token": github_config.token,
            "path": path_config,
        },
        "service_config": {
            "manager_proxy_command": None,
            "proxy_config": runner_proxy,
            "runner_proxy_config": openstack_proxy,
            "use_aproxy": True,
            "aproxy_exclude_addresses": [],
            "aproxy_redirect_ports": ["1-3127", "3129-65535"],
            "dockerhub_mirror": None,
            "ssh_debug_connections": [
                asdict(connection) for connection in ssh_debug_connections or []
            ],
            "repo_policy_compliance": None,
            "custom_pre_job_script": None,
        },
        "non_reactive_configuration": {
            "combinations": [
                {
                    "image": {
                        "name": openstack_config.image_id or "noble",
                        "labels": ["noble", "x64"],
                    },
                    "flavor": {
                        "name": openstack_config.flavor or "small",
                        "labels": ["small"],
                    },
                    "base_virtual_machines": 0 if reactive_config else 1,
                }
            ]
        },
        "reactive_configuration": (
            {
                "queue": {
                    "mongodb_uri": reactive_config.mq_uri,
                    "queue_name": reactive_config.queue_name,
                },
                "max_total_virtual_machines": reactive_config.max_total_virtual_machines,
                "images": reactive_config.images
                or [
                    {
                        "name": openstack_config.image_id or "noble",
                        "labels": ["noble", "x64"],
                    }
                ],
                "flavors": reactive_config.flavors
                or [
                    {
                        "name": openstack_config.flavor or "small",
                        "labels": ["small"],
                    }
                ],
            }
            if reactive_config
            else None
        ),
        "openstack_configuration": {
            "vm_prefix": test_config.vm_prefix,
            "network": openstack_config.network,
            "credentials": {
                "auth_url": openstack_config.auth_url,
                "project_name": openstack_config.project,
                "username": openstack_config.username,
                "password": openstack_config.password,
                "user_domain_name": openstack_config.user_domain_name,
                "project_domain_name": openstack_config.project_domain_name,
                "region_name": openstack_config.region_name,
            },
        },
        "reconcile_interval": 60,
    }
