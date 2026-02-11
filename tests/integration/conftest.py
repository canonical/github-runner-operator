# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

import json
import logging
import random
import secrets
import string
import textwrap
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, AsyncGenerator, AsyncIterator, Generator, Iterator, Optional, cast

import jubilant
import nest_asyncio
import openstack
import pytest
import pytest_asyncio
import yaml
from git import Repo
from github import Github, GithubException
from github.Auth import Token
from github.Branch import Branch
from github.Repository import Repository
from github_runner_manager.github_client import GithubClient
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Model
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

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
    MONGODB_APP_NAME,
    deploy_github_runner_charm,
    get_github_runner_manager_service_log,
    get_github_runner_metrics_log,
    get_github_runner_reactive_log,
    wait_for,
    wait_for_runner_ready,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper
from tests.status_name import ACTIVE

DEFAULT_RECONCILE_INTERVAL = 2

IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS = 30 * 60

# The following line is required because we are using request.getfixturevalue in conjunction
# with pytest-asyncio. See https://github.com/pytest-dev/pytest-asyncio/issues/112
nest_asyncio.apply()


@dataclass
class GitHubConfig:
    """GitHub configuration for tests.

    Attributes:
        token: GitHub personal access token.
        path: GitHub repository path in <owner>/<repo> or <user>/<repo> format.
    """

    token: str
    path: str


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
def charm_file(pytestconfig: pytest.Config) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "Please specify the --charm-file command line option"

    return f"./{charm}"


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
    existing_app_suffix: str,
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
        # servers, keys, security groups, security rules, images are created by the charm.
        # don't remove security groups & rules since they are single instances.
        # don't remove images since it will be moved to image-builder
        for server in servers:
            server_name: str = server.name
            if server_name.startswith(app_name):
                connection.delete_server(server_name)
        for key in connection.list_keypairs():
            key_name: str = key.name
            if key_name.startswith(app_name):
                connection.delete_keypair(key_name)


@pytest_asyncio.fixture(scope="module")
async def model(ops_test: OpsTest, proxy_config: ProxyConfig) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None
    await ops_test.model.set_config(
        {
            "juju-http-proxy": proxy_config.http_proxy,
            "juju-https-proxy": proxy_config.https_proxy,
            "juju-no-proxy": proxy_config.no_proxy,
        }
    )
    return ops_test.model


@pytest.fixture(scope="module")
def runner_manager_github_client(github_config: GitHubConfig) -> GithubClient:
    return GithubClient(token=github_config.token)


@pytest_asyncio.fixture(scope="module")
async def app_no_runner(
    model: Model,
    basic_app: Application,
) -> AsyncIterator[Application]:
    """Application with no runner."""
    await basic_app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await model.wait_for_idle(apps=[basic_app.name], status=ACTIVE, timeout=20 * 60)
    yield basic_app


@pytest_asyncio.fixture(scope="module")
async def openstack_model_proxy(
    openstack_config: OpenStackConfig,
    model: Model,
) -> None:
    await model.set_config(
        {
            "juju-http-proxy": openstack_config.http_proxy,
            "juju-https-proxy": openstack_config.https_proxy,
            "juju-no-proxy": openstack_config.no_proxy,
            "logging-config": "<root>=INFO;unit=INFO",
        }
    )


@pytest_asyncio.fixture(scope="module", name="image_builder_config")
async def image_builder_config_fixture(
    openstack_config: OpenStackConfig,
):
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


@pytest_asyncio.fixture(scope="module", name="image_builder")
async def image_builder_fixture(
    model: Model,
    existing_app_suffix: Optional[str],
    image_builder_app_name: str,
    openstack_config: OpenStackConfig,
    image_builder_config: dict,
    openstack_connection,
    request: pytest.FixtureRequest,
):
    """The image builder application for OpenStack runners.

    If openstack_config.test_image_id is provided, uses any-charm to mock the image relation.
    Otherwise, deploys the real github-runner-image-builder charm.
    """
    if existing_app_suffix:
        logging.info("Using existing image builder %s", image_builder_app_name)
        yield model.applications[image_builder_app_name]
        return

    if not openstack_config.test_image_id:
        logging.info("Deploying image builder %s", image_builder_app_name)
        # Deploy the real github-runner-image-builder
        yield await model.deploy(
            "github-runner-image-builder",
            application_name=image_builder_app_name,
            channel="latest/edge",
            config=image_builder_config,
            constraints={
                "root-disk": 20 * 1024,
                "mem": 2 * 1024,
                # 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
                # https://github.com/canonical/snapd/pull/16131
                "virt-type": "virtual-machine",
                "cores": 2,
            },
        )

        # The github-image-builder does not clean keypairs. Until it does,
        # we clean them manually here.
        logging.info("Cleaning up image builder resources...")
        for key in openstack_connection.list_keypairs():
            key_name: str = key.name
            if key_name.startswith(image_builder_app_name):
                openstack_connection.delete_keypair(key_name)

        return

    # Use any-charm to mock the image relation provider
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
                    event.relation.data[self.unit]['tags'] = 'jammy, amd64'
            """),
    }
    logging.info(
        "Deploying fake image builder via any-charm for image ID %s",
        openstack_config.test_image_id,
    )
    yield await model.deploy(
        "any-charm",
        application_name=image_builder_app_name,
        channel="latest/beta",
        config={"src-overwrite": json.dumps(any_charm_src_overwrite)},
    )


@pytest_asyncio.fixture(scope="module", name="app_openstack_runner")
async def app_openstack_runner_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    github_config: GitHubConfig,
    openstack_config: OpenStackConfig,
    existing_app_suffix: Optional[str],
    image_builder: Application,
    dockerhub_mirror: Optional[str],
    request: pytest.FixtureRequest,
) -> AsyncIterator[Application]:
    """Application launching VMs and no runners."""
    if existing_app_suffix:
        application = model.applications[app_name]
    else:
        application = await deploy_github_runner_charm(
            model=model,
            charm_file=charm_file,
            app_name=app_name,
            path=github_config.path,
            token=github_config.token,
            http_proxy=openstack_config.http_proxy,
            https_proxy=openstack_config.https_proxy,
            no_proxy=openstack_config.no_proxy,
            reconcile_interval=DEFAULT_RECONCILE_INTERVAL,
            constraints={"root-disk": 50 * 1024, "mem": 2 * 1024, "virt-type": "virtual-machine"},
            config={
                OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_config.clouds_yaml_contents,
                OPENSTACK_NETWORK_CONFIG_NAME: openstack_config.network_name,
                OPENSTACK_FLAVOR_CONFIG_NAME: openstack_config.flavor_name,
                USE_APROXY_CONFIG_NAME: bool(openstack_config.http_proxy),
                APROXY_REDIRECT_PORTS_CONFIG_NAME: "1-3127,3129-65535",
                LABELS_CONFIG_NAME: app_name,
                **({DOCKERHUB_MIRROR_CONFIG_NAME: dockerhub_mirror} if dockerhub_mirror else {}),
            },
            wait_idle=False,
        )
        await model.integrate(image_builder.name, f"{application.name}:image")
    await model.wait_for_idle(
        apps=[application.name, image_builder.name],
        status=ACTIVE,
        timeout=IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS,
    )

    yield application

    if request.session.testsfailed:
        try:
            app_log = await get_github_runner_manager_service_log(unit=application.units[0])
            logging.info("Application log: \n%s", app_log)
            reactive_log = await get_github_runner_reactive_log(unit=application.units[0])
            logging.info("Reactive log: \n%s", reactive_log)
            metrics_log = await get_github_runner_metrics_log(unit=application.units[0])
            logging.info("Metrics log: \n%s", metrics_log)
        except AssertionError:
            logging.warning("Failed to get application log.", exc_info=True)


@pytest_asyncio.fixture(scope="module", name="app_scheduled_events")
async def app_scheduled_events_fixture(
    model: Model,
    app_openstack_runner,
):
    """Application to check scheduled events."""
    application = app_openstack_runner
    await application.set_config({"reconcile-interval": "8"})
    await application.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await model.wait_for_idle(apps=[application.name], status=ACTIVE, timeout=20 * 60)
    await wait_for_runner_ready(app=application)
    return application


@pytest_asyncio.fixture(scope="module")
async def app_runner(
    model: Model,
    charm_file: str,
    app_name: str,
    github_config: GitHubConfig,
    proxy_config: ProxyConfig,
) -> AsyncIterator[Application]:
    """Application to test runners."""
    # Use a different app_name so workflows can select runners from this deployment.
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=f"{app_name}-test",
        path=github_config.path,
        token=github_config.token,
        http_proxy=proxy_config.http_proxy,
        https_proxy=proxy_config.https_proxy,
        no_proxy=proxy_config.no_proxy,
        reconcile_interval=1,
    )
    return application


@pytest_asyncio.fixture(scope="module", name="app_no_wait")
async def app_no_wait_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    github_config: GitHubConfig,
    proxy_config: ProxyConfig,
) -> AsyncIterator[Application]:
    """Github runner charm application without waiting for active."""
    app: Application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=github_config.path,
        token=github_config.token,
        http_proxy=proxy_config.http_proxy,
        https_proxy=proxy_config.https_proxy,
        no_proxy=proxy_config.no_proxy,
        reconcile_interval=1,
        wait_idle=False,
    )
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    return app


@pytest_asyncio.fixture(scope="module", name="tmate_ssh_server_app")
async def tmate_ssh_server_app_fixture(model: Model) -> AsyncIterator[Application]:
    """tmate-ssh-server charm application related to GitHub-Runner app charm."""
    tmate_app: Application = await model.deploy(
        "tmate-ssh-server",
        channel="edge",
        # 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
        # https://github.com/canonical/snapd/pull/16131
        constraints={"virt-type": "virtual-machine"},
    )
    return tmate_app


@pytest_asyncio.fixture(scope="module", name="tmate_ssh_server_unit_ip")
async def tmate_ssh_server_unit_ip_fixture(
    model: Model,
    tmate_ssh_server_app: Application,
) -> bytes | str:
    """tmate-ssh-server charm unit ip."""
    app_name = tmate_ssh_server_app.name
    status: FullStatus = await model.get_status([app_name])
    app_status = status.applications[app_name]
    assert app_status is not None, f"Application {app_name} not found in status"
    try:
        # mypy does not recognize that app_status is of type ApplicationStatus
        unit_status: UnitStatus = next(iter(app_status.units.values()))  # type: ignore
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
) -> Iterator[Repository]:
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


@pytest_asyncio.fixture(scope="module")
async def app_with_forked_repo(
    model: Model, basic_app: Application, forked_github_repository: Repository
) -> Application:
    """Application with no runner on a forked repo.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    await basic_app.set_config({PATH_CONFIG_NAME: forked_github_repository.full_name})

    return basic_app


@pytest_asyncio.fixture(scope="module", name="test_github_branch")
async def test_github_branch_fixture(github_repository: Repository) -> AsyncIterator[Branch]:
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

    await wait_for(get_branch)

    yield get_branch()

    branch_ref.delete()


@pytest_asyncio.fixture(scope="module", name="app_for_metric")
async def app_for_metric_fixture(
    basic_app: Application,
) -> AsyncIterator[Application]:
    yield basic_app


@pytest_asyncio.fixture(scope="module", name="mongodb")
async def mongodb_fixture(model: Model, existing_app_suffix: str | None) -> Application:
    """Deploy MongoDB."""
    if not existing_app_suffix:
        mongodb = await model.deploy(
            MONGODB_APP_NAME,
            channel="6/edge",
            # 2025-11-26: Set deployment type to virtual-machine due to bug with snapd. See:
            # https://github.com/canonical/snapd/pull/16131
            constraints={"virt-type": "virtual-machine"},
        )
    else:
        mongodb = model.applications["mongodb"]
    return mongodb


@pytest_asyncio.fixture(scope="module", name="app_for_reactive")
async def app_for_reactive_fixture(
    model: Model,
    mongodb: Application,
    app_openstack_runner: Application,
    existing_app_suffix: Optional[str],
) -> Application:
    """Application for testing reactive."""
    if not existing_app_suffix:
        await model.relate(f"{app_openstack_runner.name}:mongodb", f"{mongodb.name}:database")

    await model.wait_for_idle(apps=[app_openstack_runner.name, mongodb.name], status=ACTIVE)

    return app_openstack_runner


@pytest_asyncio.fixture(scope="module", name="basic_app")
async def basic_app_fixture(request: pytest.FixtureRequest) -> Application:
    """Setup the charm with the basic configuration."""
    return request.getfixturevalue("app_openstack_runner")


@pytest_asyncio.fixture(scope="function", name="instance_helper")
async def instance_helper_fixture(request: pytest.FixtureRequest) -> OpenStackInstanceHelper:
    """Instance helper fixture."""
    openstack_connection = request.getfixturevalue("openstack_connection")
    return OpenStackInstanceHelper(openstack_connection=openstack_connection)


@pytest_asyncio.fixture(scope="module")
async def juju(
    request: pytest.FixtureRequest, model: Model
) -> AsyncGenerator[jubilant.Juju, None]:
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""

    def show_debug_log(juju: jubilant.Juju):
        """Show debug log if tests failed.

        Args:
            juju: The jubilant.Juju instance.
        """
        if request.session.testsfailed:
            log = juju.debug_log(limit=1000)
            print(log, end="")

    controller = await model.get_controller()
    if model:
        # Currently juju has no way of switching controller context, this is required to operate
        # in the right controller's right model when using multiple controllers.
        # See: https://github.com/canonical/jubilant/issues/158
        juju = jubilant.Juju(model=f"{controller.controller_name}:{model.name}")
        yield juju
        show_debug_log(juju)
        return

    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models, controller=controller.controller_name) as juju:
        juju.model = f"{controller.controller_name}:{juju.model}"
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return


@pytest.fixture(scope="module")
def planner_token_secret_name() -> str:
    """Planner token secret name."""
    return "planner-token-secret"


@pytest_asyncio.fixture(scope="module")
async def planner_token_secret(model: Model, planner_token_secret_name: str) -> str:
    """Create a planner token secret."""
    return await model.add_secret(
        name=planner_token_secret_name, data_args=["token=MOCK_PLANNER_TOKEN"]
    )


@pytest_asyncio.fixture(scope="module")
async def mock_planner_app(model: Model, planner_token_secret) -> AsyncIterator[Application]:
    planner_name = "planner"

    any_charm_src_overwrite = {
        "planner.py": textwrap.dedent("""\
            import json
            import sys
            from http.server import BaseHTTPRequestHandler, HTTPServer
            from pathlib import Path

            FLAVOR_FILE = Path("/tmp/planner_flavor.json")

            def run_server(address):
                server = HTTPServer(server_address=(address, 8080), RequestHandlerClass=MockPlannerHandler)
                server.serve_forever()

            class MockPlannerHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if FLAVOR_FILE.exists():
                        data = FLAVOR_FILE.read_text(encoding="utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(data.encode())
                    else:
                        self.send_response(404)
                        self.end_headers()

            if __name__ == "__main__":
                run_server(sys.argv[1])
            """),
        "any_charm.py": textwrap.dedent(f"""\
            import json
            import signal
            import subprocess
            import os
            from pathlib import Path
            from any_charm_base import AnyCharmBase

            FLAVOR_FILE = Path("/tmp/planner_flavor.json")

            class AnyCharm(AnyCharmBase):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.framework.observe(self.on.install, self._on_install)
                    self.framework.observe(self.on["provide-github-runner-planner-v0"].relation_changed, self._on_planner_relation_changed)

                def _on_install(self, _):
                    address = str(self.model.get_binding("juju-info").network.bind_address)
                    pid_file = Path("/tmp/any.pid")
                    if pid_file.exists():
                        try:
                            os.kill(int(pid_file.read_text(encoding="utf8")), signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        pid_file.unlink()
                    with open("planner.log", "a") as log_file:
                        proc_http = subprocess.Popen(["python3", "-m", "planner", address, "&"], start_new_session=True, cwd=str(Path.cwd() / "src"), stdout=log_file, stderr=subprocess.STDOUT)
                    pid_file.write_text(str(proc_http.pid), encoding="utf8")

                def _on_planner_relation_changed(self, event):
                    event.relation.data[self.unit]["endpoint"] = "http://" + str(self.model.get_binding("juju-info").network.bind_address) + ":8080"
                    event.relation.data[self.unit]["token"] = "{planner_token_secret}"
                    app_data = event.relation.data[event.app]
                    flavor = app_data.get("flavor")
                    if flavor:
                        data = {{
                            "flavor": flavor,
                            "flavor-labels": app_data.get("flavor-labels", ""),
                            "flavor-platform": app_data.get("flavor-platform", ""),
                            "flavor-priority": app_data.get("flavor-priority", ""),
                            "flavor-minimum-pressure": app_data.get("flavor-minimum-pressure", ""),
                        }}
                        FLAVOR_FILE.write_text(json.dumps(data), encoding="utf-8")
            """),
    }

    planner_app: Application = await model.deploy(
        "any-charm",
        planner_name,
        channel="latest/beta",
        config={"src-overwrite": json.dumps(any_charm_src_overwrite)},
    )

    await model.wait_for_idle(apps=[planner_app.name], status=ACTIVE, timeout=10 * 60)
    yield planner_app
