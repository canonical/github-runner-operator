# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

import json
import logging
import random
import re
import secrets
import string
import textwrap
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, Generator, Iterator, Optional, cast

import jubilant
import openstack
import pytest
import yaml
from git import Repo
from github import Github, GithubException
from github.Auth import Token
from github.Branch import Branch
from github.Repository import Repository
from openstack.connection import Connection

from charm_state import (
    APROXY_REDIRECT_PORTS_CONFIG_NAME,
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
    DOCKERHUB_MIRROR_CONFIG_NAME,
    LABELS_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    OPENSTACK_NETWORK_CONFIG_NAME,
    PATH_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
)
from tests.integration.helpers.common import (
    deploy_github_runner_charm,
    get_github_runner_manager_service_log,
    get_github_runner_metrics_log,
    wait_for,
    wait_for_runner_ready,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper

DEFAULT_RECONCILE_INTERVAL = 2

IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS = 30 * 60


@dataclass
class GitHubConfig:
    """GitHub configuration for tests.

    Attributes:
        token: GitHub personal access token (always required for test harness API calls).
        path: GitHub repository path in <owner>/<repo> or <user>/<repo> format.
        app_client_id: GitHub App Client ID (optional, for App auth testing).
        installation_id: GitHub App installation ID (optional, for App auth testing).
        private_key: GitHub App PEM-encoded private key (optional, for App auth testing).
        has_app_auth: Whether GitHub App authentication credentials are configured.
    """

    token: str
    path: str
    app_client_id: str | None = None
    installation_id: int | None = None
    private_key: str | None = None

    @property
    def has_app_auth(self) -> bool:
        """Whether GitHub App authentication credentials are configured."""
        return all((self.app_client_id, self.installation_id, self.private_key))


@dataclass
class OpenStackConfig:
    """OpenStack configuration for tests.

    Attributes:
        http_proxy: HTTP proxy for OpenStack runners.
        https_proxy: HTTPS proxy for OpenStack runners.
        no_proxy: No proxy configuration for OpenStack runners.
        network_name: Network to spawn test instances under.
        flavor_name: Flavor to create testing instances with.
        auth_url: OpenStack authentication URL (Keystone).
        password: OpenStack password.
        project_domain_name: OpenStack project domain to use.
        project_name: OpenStack project to use within the domain.
        user_domain_name: OpenStack user domain to use.
        username: OpenStack user to use within the domain.
        region_name: OpenStack deployment region.
        test_image_id: Test image ID for mocking image builder (optional).
        clouds_yaml_contents: Generated clouds.yaml configuration from OpenStack settings.
    """

    http_proxy: str
    https_proxy: str
    no_proxy: str
    network_name: str
    flavor_name: str
    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str
    region_name: str
    test_image_id: Optional[str] = None

    @property
    def clouds_yaml_contents(self) -> str:
        """Generate clouds.yaml contents from configuration."""
        return string.Template(
            Path("tests/integration/data/clouds.yaml.tmpl").read_text(encoding="utf-8")
        ).substitute(
            {
                "auth_url": self.auth_url,
                "password": self.password,
                "project_domain_name": self.project_domain_name,
                "project_name": self.project_name,
                "user_domain_name": self.user_domain_name,
                "username": self.username,
                "region_name": self.region_name,
            }
        )


@dataclass
class ProxyConfig:
    """Proxy configuration for tests.

    Attributes:
        http_proxy: HTTP proxy for runners.
        https_proxy: HTTPS proxy for runners.
        no_proxy: No proxy configuration for runners.
    """

    http_proxy: str
    https_proxy: str
    no_proxy: str


# Map base token to (charm base, series)
BASE_SERIES_MAP: dict[str, tuple[str, str]] = {
    "22.04": ("ubuntu@22.04", "jammy"),
    "24.04": ("ubuntu@24.04", "noble"),
}


@dataclass
class CharmArtifact:
    """Charm build artifact metadata used for selection.

    Attributes:
        name: Artifact filename relative to the workspace root.
        base_token: Base identifier extracted from the filename (e.g., '22.04', '24.04').
    """

    name: str
    base_token: str


@dataclass
class DeploymentContext:
    """Deployment parameters derived from the selected artifact.

    Attributes:
        charm_path: Filesystem path to the selected charm artifact.
        base: Juju base for deployment (e.g., 'ubuntu@22.04').
        series: Ubuntu series corresponding to the base (e.g., 'jammy', 'noble').
    """

    charm_path: str
    base: str
    series: str


def _parse_base_token(artifact_name: str) -> str:
    """Extract an Ubuntu base token (e.g., '22.04', '24.04', '26.04') from an artifact name."""
    ubuntu_match = re.search(r"ubuntu@(?P<base>\d{2}\.\d{2})", artifact_name)
    assert ubuntu_match, "Base not detected from charm file (e.g., 'github-runner-ubuntu@22.04')"
    return ubuntu_match.group("base")


def resolve_series(base_token: str) -> tuple[str, str]:
    """Resolve Juju base and Ubuntu series for a given base token.

    Args:
        base_token: Ubuntu base identifier (e.g., '22.04', '24.04').

    Returns:
        A tuple of (charm base, series), for example ('ubuntu@22.04', 'jammy').

    Raises:
        ValueError: if the base token is unknown. Update BASE_SERIES_MAP
            when new Ubuntu releases are supported.
    """
    mapped = BASE_SERIES_MAP.get(base_token)
    if not mapped:
        raise ValueError(
            f"Unknown base token '{base_token}'. Please update BASE_SERIES_MAP to include"
            " the corresponding series."
        )
    return mapped


@pytest.fixture(scope="module")
def cli_base_option(pytestconfig: pytest.Config) -> str:
    """Selected base token from `--base` option, defaulting to '22.04'."""
    return cast(str, pytestconfig.getoption("--base") or "22.04")


@pytest.fixture(scope="module")
def available_charm_files(pytestconfig: pytest.Config) -> list[str]:
    """List of charm artifact filenames from repeated `--charm-file` options.

    Asserts that at least one artifact is provided.
    """
    files: list[str] = cast(list[str], pytestconfig.getoption("--charm-file") or [])
    assert files, "Please specify one or more --charm-file options"
    return files


@pytest.fixture(scope="module")
def artifact_catalog(available_charm_files: list[str]) -> list[CharmArtifact]:
    """Build a catalog of charm artifacts annotated with base tokens."""
    catalog: list[CharmArtifact] = []
    for f in available_charm_files:
        base_token = _parse_base_token(f)
        catalog.append(CharmArtifact(name=f, base_token=base_token))
    return catalog


@pytest.fixture(scope="module")
def selected_artifact(
    cli_base_option: str, artifact_catalog: list[CharmArtifact]
) -> CharmArtifact:
    """Choose the artifact matching the `--base` option."""
    for art in artifact_catalog:
        if art.base_token == cli_base_option:
            return art
    raise ValueError(
        "No charm artifact found matching the specified base token. Please check your"
        " --charm-file options."
    )


@pytest.fixture(scope="module")
def deployment_context(selected_artifact: CharmArtifact) -> DeploymentContext:
    """Construct the deployment context (base, series) for the selected artifact.

    Fails fast if the base token isn't mapped to a known series.
    """
    base, series = resolve_series(selected_artifact.base_token)
    return DeploymentContext(
        charm_path=f"./{selected_artifact.name}",
        base=base,
        series=series,
    )


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    """Metadata information of the charm."""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def existing_app_suffix(pytestconfig: pytest.Config) -> Optional[str]:
    """The existing application name suffix to use for the test."""
    return pytestconfig.getoption("--use-existing-app-suffix")


@pytest.fixture(scope="module")
def random_app_name_suffix(existing_app_suffix: Optional[str]) -> str:
    """Randomized application name."""
    # Randomized suffix name to avoid collision when runner is connecting to GitHub.
    return existing_app_suffix or (
        random.choice(string.ascii_lowercase)
        + "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
    )


@pytest.fixture(scope="module")
def app_name(random_app_name_suffix: str) -> str:
    """Randomized application name."""
    return f"test-{random_app_name_suffix}"


@pytest.fixture(scope="module")
def image_builder_app_name(random_app_name_suffix: str) -> str:
    """Randomized application name."""
    return f"github-runner-image-builder-{random_app_name_suffix}"


@pytest.fixture(scope="module")
def github_config(pytestconfig: pytest.Config) -> GitHubConfig:
    """Github configuration for tests.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        GitHub configuration object.
    """
    token = pytestconfig.getoption("--token")
    assert token, "Please specify the --token command line option"
    tokens = {token.strip() for token in token.split(",")}
    random_token = random.choice(list(tokens))

    path = pytestconfig.getoption("--path")
    assert path, (
        "Please specify the --path command line option with repository "
        "path of <org>/<repo> or <user>/<repo> format."
    )

    return GitHubConfig(token=random_token, path=path)


@pytest.fixture(scope="module")
def proxy_config(pytestconfig: pytest.Config) -> ProxyConfig:
    """Proxy configuration for tests.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        Proxy configuration object.
    """
    http_proxy = pytestconfig.getoption("--http-proxy")
    https_proxy = pytestconfig.getoption("--https-proxy")
    no_proxy = pytestconfig.getoption("--no-proxy")

    return ProxyConfig(
        http_proxy="" if http_proxy is None else http_proxy,
        https_proxy="" if https_proxy is None else https_proxy,
        no_proxy="" if no_proxy is None else no_proxy,
    )


@pytest.fixture(scope="module")
def openstack_config(pytestconfig: pytest.Config) -> OpenStackConfig:
    """Openstack configuration for tests.

    Args:
        pytestconfig: Pytest configuration object.

    Returns:
        OpenStack configuration object.
    """
    http_proxy = pytestconfig.getoption("--openstack-http-proxy")
    https_proxy = pytestconfig.getoption("--openstack-https-proxy")
    no_proxy = pytestconfig.getoption("--openstack-no-proxy")

    network_name = pytestconfig.getoption("--openstack-network-name")
    assert network_name, "Please specify the --openstack-network-name command line option"

    flavor_name = pytestconfig.getoption("--openstack-flavor-name")
    assert flavor_name, "Please specify the --openstack-flavor-name command line option"

    # OpenStack authentication details
    auth_url = pytestconfig.getoption("--openstack-auth-url")
    password = pytestconfig.getoption("--openstack-password")
    assert (
        password
    ), "Please specify the --openstack-password option or OS_PASSWORD environment variable"
    project_domain_name = pytestconfig.getoption("--openstack-project-domain-name")
    project_name = pytestconfig.getoption("--openstack-project-name")
    user_domain_name = pytestconfig.getoption("--openstack-user-domain-name")
    username = pytestconfig.getoption("--openstack-username")
    region_name = pytestconfig.getoption("--openstack-region-name")

    assert all(
        [
            auth_url,
            password,
            project_domain_name,
            project_name,
            user_domain_name,
            username,
            region_name,
        ]
    ), "Specify all OpenStack private endpoint options."

    test_image_id = pytestconfig.getoption("--openstack-image-id")

    return OpenStackConfig(
        http_proxy="" if http_proxy is None else http_proxy,
        https_proxy="" if https_proxy is None else https_proxy,
        no_proxy="" if no_proxy is None else no_proxy,
        network_name=network_name,
        flavor_name=flavor_name,
        auth_url=auth_url,
        password=str(password),
        project_domain_name=project_domain_name,
        project_name=project_name,
        user_domain_name=user_domain_name,
        username=username,
        region_name=region_name,
        test_image_id=test_image_id,
    )


@pytest.fixture(scope="module")
def dockerhub_mirror(pytestconfig: pytest.Config) -> Optional[str]:
    """The dockerhub mirror URL for tests.

    Returns:
        The dockerhub mirror URL if provided, None otherwise.
    """
    return pytestconfig.getoption("--dockerhub-mirror")


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(
    openstack_config: OpenStackConfig,
    app_name: str,
    existing_app_suffix: Optional[str],
    juju: jubilant.Juju,
    request: pytest.FixtureRequest,
) -> Generator[Connection, None, None]:
    """The openstack connection instance."""
    clouds_yaml = yaml.safe_load(openstack_config.clouds_yaml_contents)
    clouds_yaml_path = Path.cwd() / "clouds.yaml"
    clouds_yaml_path.write_text(data=openstack_config.clouds_yaml_contents, encoding="utf-8")
    first_cloud = next(iter(clouds_yaml["clouds"].keys()))
    with openstack.connect(first_cloud) as connection:
        yield connection

    servers = connection.list_servers(filters={"name": app_name})

    if request.session.testsfailed:
        logging.info("OpenStack servers: %s", servers)
        for server in servers:
            console_log = connection.get_server_console(server=server)
            logging.info("Server %s console log:\n%s", server.name, console_log)

    if not existing_app_suffix:
        for server in servers:
            server_name: str = server.name
            if server_name.startswith(app_name):
                connection.delete_server(server_name)
        for key in connection.list_keypairs():
            key_name: str = key.name
            if key_name.startswith(app_name):
                connection.delete_keypair(key_name)


@pytest.fixture(scope="module")
def juju(
    request: pytest.FixtureRequest,
    proxy_config: ProxyConfig,
) -> Generator[jubilant.Juju, None, None]:
    """Pytest fixture that creates a temporary Juju model for integration tests."""
    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as j:
        j.wait_timeout = 20 * 60
        j.model_config(
            values={
                "juju-http-proxy": proxy_config.http_proxy,
                "juju-https-proxy": proxy_config.https_proxy,
                "juju-no-proxy": proxy_config.no_proxy,
                "logging-config": "<root>=INFO;unit=INFO",
            }
        )
        yield j
        if request.session.testsfailed:
            log = j.debug_log(limit=1000)
            print(log, end="")


@pytest.fixture(scope="module")
def app_no_runner(
    juju: jubilant.Juju,
    basic_app: str,
) -> Iterator[str]:
    """Application with no runner."""
    juju.config(basic_app, values={BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    juju.wait(
        lambda status: jubilant.all_active(status, basic_app),
        timeout=20 * 60,
    )
    yield basic_app


@pytest.fixture(scope="module")
def openstack_model_proxy(
    openstack_config: OpenStackConfig,
    juju: jubilant.Juju,
) -> None:
    """Set model proxy config for OpenStack environments."""
    juju.model_config(
        values={
            "juju-http-proxy": openstack_config.http_proxy,
            "juju-https-proxy": openstack_config.https_proxy,
            "juju-no-proxy": openstack_config.no_proxy,
            "logging-config": "<root>=INFO;unit=INFO",
        }
    )


@pytest.fixture(scope="module", name="image_builder_config")
def image_builder_config_fixture(
    openstack_config: OpenStackConfig,
) -> dict:
    """The image builder application default for OpenStack runners."""
    return {
        "build-interval": "12",
        "revision-history-limit": "2",
        "openstack-auth-url": openstack_config.auth_url,
        # Bandit thinks this is a hardcoded password
        "openstack-password": openstack_config.password,  # nosec: B105
        "openstack-project-domain-name": openstack_config.project_domain_name,
        "openstack-project-name": openstack_config.project_name,
        "openstack-user-domain-name": openstack_config.user_domain_name,
        "openstack-user-name": openstack_config.username,
        "build-flavor": openstack_config.flavor_name,
        "build-network": openstack_config.network_name,
        "architecture": "amd64",
    }


@pytest.fixture(scope="module", name="image_builder")
def image_builder_fixture(
    juju: jubilant.Juju,
    existing_app_suffix: Optional[str],
    image_builder_app_name: str,
    openstack_config: OpenStackConfig,
    image_builder_config: dict,
    openstack_connection: Connection,
    request: pytest.FixtureRequest,
) -> Iterator[str]:
    """The image builder application for OpenStack runners.

    If openstack_config.test_image_id is provided, uses any-charm to mock the image relation.
    Otherwise, deploys the real github-runner-image-builder charm.
    """
    if existing_app_suffix:
        logging.info("Using existing image builder %s", image_builder_app_name)
        yield image_builder_app_name
        return

    if not openstack_config.test_image_id:
        logging.info("Deploying image builder %s", image_builder_app_name)
        juju.deploy(
            "github-runner-image-builder",
            app=image_builder_app_name,
            channel="latest/edge",
            config=image_builder_config,
            constraints={
                "root-disk": "20480M",
                "mem": "2048M",
                # 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
                # https://github.com/canonical/snapd/pull/16131
                "virt-type": "virtual-machine",
                "cores": "2",
            },
            log=False,
        )

        yield image_builder_app_name

        # The github-image-builder does not clean keypairs. Until it does,
        # we clean them manually here.
        logging.info("Cleaning up image builder resources...")
        for key in openstack_connection.list_keypairs():
            key_name: str = key.name
            if key_name.startswith(image_builder_app_name):
                openstack_connection.delete_keypair(key_name)

        return

    # Use any-charm to mock the image relation provider
    dep_ctx: DeploymentContext = request.getfixturevalue("deployment_context")
    series = dep_ctx.series

    any_charm_src_overwrite = {
        "any_charm.py": textwrap.dedent(f"""\
            from any_charm_base import AnyCharmBase

            class AnyCharm(AnyCharmBase):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.framework.observe(self.on['provide-github-runner-image-v0'].\
relation_changed, self._image_relation_changed)

                def _image_relation_changed(self, event):
                    # Provide mock image relation data
                    event.relation.data[self.unit]['id'] = '{openstack_config.test_image_id}'
                    event.relation.data[self.unit]['tags'] = '{series}, amd64'
            """),
    }
    logging.info(
        "Deploying fake image builder via any-charm for image ID %s",
        openstack_config.test_image_id,
    )
    juju.deploy(
        "any-charm",
        app=image_builder_app_name,
        channel="latest/beta",
        config={"src-overwrite": json.dumps(any_charm_src_overwrite)},
    )
    yield image_builder_app_name


@pytest.fixture(scope="module", name="app_openstack_runner")
def app_openstack_runner_fixture(
    juju: jubilant.Juju,
    deployment_context: DeploymentContext,
    app_name: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    existing_app_suffix: Optional[str],
    image_builder: str,
    dockerhub_mirror: Optional[str],
    request: pytest.FixtureRequest,
) -> Iterator[str]:
    """Application launching VMs and no runners."""
    if existing_app_suffix:
        application_name = app_name
    else:
        application_name = deploy_github_runner_charm(
            juju=juju,
            charm_file=deployment_context.charm_path,
            app_name=app_name,
            github_config=github_config,
            proxy_config=ProxyConfig(
                http_proxy=openstack_config.http_proxy,
                https_proxy=openstack_config.https_proxy,
                no_proxy=openstack_config.no_proxy,
            ),
            reconcile_interval=DEFAULT_RECONCILE_INTERVAL,
            constraints={
                "root-disk": "51200M",
                "mem": "2048M",
                "virt-type": "virtual-machine",
            },
            config={
                OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_config.clouds_yaml_contents,
                OPENSTACK_NETWORK_CONFIG_NAME: openstack_config.network_name,
                OPENSTACK_FLAVOR_CONFIG_NAME: openstack_config.flavor_name,
                USE_APROXY_CONFIG_NAME: bool(openstack_config.http_proxy),
                APROXY_REDIRECT_PORTS_CONFIG_NAME: "1-3127,3129-65535",
                LABELS_CONFIG_NAME: app_name,
                **({DOCKERHUB_MIRROR_CONFIG_NAME: dockerhub_mirror} if dockerhub_mirror else {}),
            },
            base=deployment_context.base,
            wait_idle=False,
        )
        juju.integrate(image_builder, f"{application_name}:image")
    juju.wait(
        lambda status: jubilant.all_active(status, application_name, image_builder),
        timeout=IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS,
    )

    yield application_name

    if request.session.testsfailed:
        try:
            unit_name = f"{application_name}/0"
            app_log = get_github_runner_manager_service_log(juju=juju, unit_name=unit_name)
            logging.info("Application log: \n%s", app_log)
            metrics_log = get_github_runner_metrics_log(juju=juju, unit_name=unit_name)
            logging.info("Metrics log: \n%s", metrics_log)
        except AssertionError:
            logging.warning("Failed to get application log.", exc_info=True)


@pytest.fixture(scope="module", name="app_scheduled_events")
def app_scheduled_events_fixture(
    juju: jubilant.Juju,
    app_openstack_runner: str,
) -> str:
    """Application to check scheduled events."""
    juju.config(app_openstack_runner, values={"reconcile-interval": "8"})
    juju.config(app_openstack_runner, values={BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    juju.wait(
        lambda status: jubilant.all_active(status, app_openstack_runner),
        timeout=20 * 60,
    )
    wait_for_runner_ready(juju, app_openstack_runner)
    return app_openstack_runner


@pytest.fixture(scope="module")
def app_runner(
    juju: jubilant.Juju,
    deployment_context: DeploymentContext,
    app_name: str,
    github_config: GitHubConfig,
    proxy_config: ProxyConfig,
) -> str:
    """Application to test runners."""
    # Use a different app_name so workflows can select runners from this deployment.
    return deploy_github_runner_charm(
        juju=juju,
        charm_file=deployment_context.charm_path,
        app_name=f"{app_name}-test",
        github_config=github_config,
        proxy_config=proxy_config,
        reconcile_interval=1,
        base=deployment_context.base,
    )


@pytest.fixture(scope="module", name="app_no_wait")
def app_no_wait_fixture(
    juju: jubilant.Juju,
    deployment_context: DeploymentContext,
    app_name: str,
    github_config: GitHubConfig,
    proxy_config: ProxyConfig,
) -> str:
    """Github runner charm application without waiting for active."""
    deployed_name = deploy_github_runner_charm(
        juju=juju,
        charm_file=deployment_context.charm_path,
        app_name=app_name,
        github_config=github_config,
        proxy_config=proxy_config,
        reconcile_interval=1,
        base=deployment_context.base,
        wait_idle=False,
    )
    juju.config(deployed_name, values={BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    return deployed_name


@pytest.fixture(scope="module", name="tmate_ssh_server_app")
def tmate_ssh_server_app_fixture(juju: jubilant.Juju) -> str:
    """tmate-ssh-server charm application related to GitHub-Runner app charm."""
    tmate_app_name = "tmate-ssh-server"
    juju.deploy(
        tmate_app_name,
        channel="edge",
        # 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
        # https://github.com/canonical/snapd/pull/16131
        constraints={"virt-type": "virtual-machine"},
    )
    return tmate_app_name


@pytest.fixture(scope="module", name="tmate_ssh_server_unit_ip")
def tmate_ssh_server_unit_ip_fixture(
    juju: jubilant.Juju,
    tmate_ssh_server_app: str,
) -> str:
    """tmate-ssh-server charm unit ip."""
    status = juju.status()
    app_status = status.apps.get(tmate_ssh_server_app)
    assert app_status is not None, f"Application {tmate_ssh_server_app} not found in status"
    try:
        unit_status = next(iter(app_status.units.values()))
        assert unit_status.public_address, "Invalid unit address"
        return unit_status.public_address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest.fixture(scope="module")
def github_client(github_config: GitHubConfig) -> Github:
    """Returns the github client."""
    gh = Github(auth=Token(token=github_config.token))
    rate_limit = gh.get_rate_limit()
    logging.info("GitHub token rate limit: %s", rate_limit.rate)
    return gh


@pytest.fixture(scope="module")
def github_repository(github_client: Github, github_config: GitHubConfig) -> Repository:
    """Returns client to the Github repository."""
    return github_client.get_repo(github_config.path)


@pytest.fixture(scope="module")
def forked_github_repository(
    github_repository: Repository,
) -> Repository:
    """Create a fork for a GitHub repository."""
    # After fork creation, the repository workflow run must be enabled manually. Otherwise, a 404
    # on the workflow get API will be returned.
    forked_repository = github_repository.create_fork(name=f"test-{github_repository.name}")

    # Wait for repo to be ready
    for _ in range(10):
        try:
            sleep(10)
            forked_repository.get_branches()
            break
        except GithubException:
            pass
    else:
        assert False, "timed out whilst waiting for repository creation"

    return forked_repository

    # Parallel runs of this test module is allowed. Therefore, the forked repo is not removed.


@pytest.fixture(scope="module")
def forked_github_branch(
    github_repository: Repository, forked_github_repository: Repository
) -> Iterator[Branch]:
    """Create a new forked branch for testing."""
    branch_name = f"test/{secrets.token_hex(4)}"

    main_branch = forked_github_repository.get_branch(github_repository.default_branch)
    branch_ref = forked_github_repository.create_git_ref(
        ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha
    )

    for _ in range(10):
        try:
            branch = forked_github_repository.get_branch(branch_name)
            break
        except GithubException as err:
            if err.status == 404:
                sleep(5)
                continue
            raise
    else:
        assert (
            False
        ), "Failed to get created branch in fork repo, the issue with GitHub or network."

    yield branch

    branch_ref.delete()


@pytest.fixture(scope="module")
def app_with_forked_repo(
    juju: jubilant.Juju, basic_app: str, forked_github_repository: Repository
) -> str:
    """Application with no runner on a forked repo.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    juju.config(basic_app, values={PATH_CONFIG_NAME: forked_github_repository.full_name})

    return basic_app


@pytest.fixture(scope="module", name="test_github_branch")
def test_github_branch_fixture(github_repository: Repository) -> Iterator[Branch]:
    """Create a new branch for testing, from latest commit in current branch."""
    test_branch = f"test-{secrets.token_hex(4)}"
    branch_ref = github_repository.create_git_ref(
        ref=f"refs/heads/{test_branch}", sha=Repo().head.commit.hexsha
    )

    def get_branch():
        """Get newly created branch.

        Raises:
            GithubException: if unexpected GithubException has happened apart from repository not \
                found.

        Returns:
            New branch if successful, False otherwise.
        """
        try:
            branch = github_repository.get_branch(test_branch)
        except GithubException as err:
            if err.status == 404:
                return False
            raise
        return branch

    wait_for(get_branch)

    yield get_branch()

    branch_ref.delete()


@pytest.fixture(scope="module", name="basic_app")
def basic_app_fixture(request: pytest.FixtureRequest) -> str:
    """Setup the charm with the basic configuration."""
    return request.getfixturevalue("app_openstack_runner")


@pytest.fixture(scope="function", name="instance_helper")
def instance_helper_fixture(
    request: pytest.FixtureRequest,
    juju: jubilant.Juju,
) -> OpenStackInstanceHelper:
    """Instance helper fixture."""
    openstack_connection = request.getfixturevalue("openstack_connection")
    return OpenStackInstanceHelper(openstack_connection=openstack_connection, juju=juju)


@pytest.fixture(scope="module")
def planner_token_secret_name() -> str:
    """Planner token secret name."""
    return "planner-token-secret"


@pytest.fixture(scope="module")
def planner_token_secret(juju: jubilant.Juju, planner_token_secret_name: str) -> str:
    """Create a planner token secret."""
    return str(
        juju.add_secret(
            name=planner_token_secret_name,
            content={"token": "MOCK_PLANNER_TOKEN"},
        )
    )


@pytest.fixture(scope="module")
def mock_planner_app(juju: jubilant.Juju, planner_token_secret: str) -> Iterator[str]:
    """Deploy a minimal any-charm that acts as the requires side of the planner relation."""
    planner_name = "planner"

    any_charm_src_overwrite = {
        "any_charm.py": textwrap.dedent(f"""\
            from any_charm_base import AnyCharmBase

            class AnyCharm(AnyCharmBase):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.framework.observe(
                        self.on["provide-github-runner-planner-v0"].relation_changed,
                        self._on_planner_relation_changed,
                    )

                def _on_planner_relation_changed(self, event):
                    event.relation.data[self.app]["endpoint"] = "http://mock:8080"
                    event.relation.data[self.app]["token"] = "{planner_token_secret}"
            """),
    }

    juju.deploy(
        "any-charm",
        app=planner_name,
        channel="latest/beta",
        config={"src-overwrite": json.dumps(any_charm_src_overwrite)},
    )

    juju.wait(
        lambda status: jubilant.all_active(status, planner_name),
        timeout=10 * 60,
    )
    yield planner_name
