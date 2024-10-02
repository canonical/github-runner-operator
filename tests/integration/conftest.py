# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import logging
import random
import secrets
import string
from pathlib import Path
from time import sleep
from typing import Any, AsyncIterator, Generator, Iterator, Optional

import nest_asyncio
import openstack
import pytest
import pytest_asyncio
import yaml
from git import Repo
from github import Github, GithubException
from github.Branch import Branch
from github.Repository import Repository
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Model
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

from charm_state import (
    LABELS_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    OPENSTACK_FLAVOR_CONFIG_NAME,
    OPENSTACK_NETWORK_CONFIG_NAME,
    PATH_CONFIG_NAME,
    USE_APROXY_CONFIG_NAME,
    VIRTUAL_MACHINES_CONFIG_NAME,
    InstanceType,
)
from github_client import GithubClient
from tests.integration.helpers.common import (
    MONGODB_APP_NAME,
    InstanceHelper,
    deploy_github_runner_charm,
    inject_lxd_profile,
    reconcile,
    wait_for,
)
from tests.integration.helpers.lxd import LXDInstanceHelper, ensure_charm_has_runner
from tests.integration.helpers.openstack import OpenStackInstanceHelper, PrivateEndpointConfigs
from tests.status_name import ACTIVE

# The following line is required because we are using request.getfixturevalue in conjunction
# with pytest-asyncio. See https://github.com/pytest-dev/pytest-asyncio/issues/112
nest_asyncio.apply()


@pytest_asyncio.fixture(scope="module", name="instance_type")
async def instance_type_fixture(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> InstanceType:
    # Due to scope being module we cannot use request.node.get_closes_marker as openstack
    # mark is not available in this scope.
    openstack_marker = pytestconfig.getoption("-m") == "openstack"

    if openstack_marker:
        return InstanceType.OPENSTACK
    else:
        return InstanceType.LOCAL_LXD


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    """Metadata information of the charm."""
    metadata = Path("./metadata.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture(scope="module")
def existing_app(pytestconfig: pytest.Config) -> Optional[str]:
    """The existing application name to use for the test."""
    return pytestconfig.getoption("--use-existing-app")


@pytest.fixture(scope="module")
def app_name(existing_app: Optional[str]) -> str:
    """Randomized application name."""
    # Randomized app name to avoid collision when runner is connecting to GitHub.
    return existing_app or f"test-{secrets.token_hex(4)}"


@pytest.fixture(scope="module", name="openstack_clouds_yaml")
def openstack_clouds_yaml_fixture(pytestconfig: pytest.Config) -> str | None:
    """The openstack clouds yaml config."""
    return pytestconfig.getoption("--openstack-clouds-yaml")


@pytest.fixture(scope="module")
def charm_file(
    pytestconfig: pytest.Config, loop_device: Optional[str], openstack_clouds_yaml: Optional[str]
) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "Please specify the --charm-file command line option"
    charm_path_str = f"./{charm}"

    if openstack_clouds_yaml:
        return charm_path_str

    inject_lxd_profile(charm_file=Path(charm_path_str), loop_device=loop_device)
    return charm_path_str


@pytest.fixture(scope="module")
def path(pytestconfig: pytest.Config) -> str:
    """Configured path setting."""
    path = pytestconfig.getoption("--path")
    assert path, (
        "Please specify the --path command line option with repository "
        "path of <org>/<repo> or <user>/<repo> format."
    )
    return path


@pytest.fixture(scope="module")
def token(pytestconfig: pytest.Config) -> str:
    """Configured token setting."""
    token = pytestconfig.getoption("--token")
    assert token, "Please specify the --token command line option"
    tokens = {token.strip() for token in token.split(",")}
    random_token = random.choice(list(tokens))
    return random_token


@pytest.fixture(scope="module")
def token_alt(pytestconfig: pytest.Config, token: str) -> str:
    """Configured token_alt setting."""
    token_alt = pytestconfig.getoption("--token-alt")
    assert token_alt, (
        "Please specify the --token-alt command line option with GitHub Personal "
        "Access Token value."
    )
    assert token_alt != token, "Please specify a different token for --token-alt"
    return token_alt


@pytest.fixture(scope="module")
def http_proxy(pytestconfig: pytest.Config) -> str:
    """Configured http_proxy setting."""
    http_proxy = pytestconfig.getoption("--http-proxy")
    return "" if http_proxy is None else http_proxy


@pytest.fixture(scope="module")
def https_proxy(pytestconfig: pytest.Config) -> str:
    """Configured https_proxy setting."""
    https_proxy = pytestconfig.getoption("--https-proxy")
    return "" if https_proxy is None else https_proxy


@pytest.fixture(scope="module")
def no_proxy(pytestconfig: pytest.Config) -> str:
    """Configured no_proxy setting."""
    no_proxy = pytestconfig.getoption("--no-proxy")
    return "" if no_proxy is None else no_proxy


@pytest.fixture(scope="module", name="openstack_http_proxy")
def openstack_http_proxy_fixture(pytestconfig: pytest.Config) -> str:
    """Configured http_proxy setting for openstack runners."""
    http_proxy = pytestconfig.getoption("--openstack-http-proxy")
    return "" if http_proxy is None else http_proxy


@pytest.fixture(scope="module", name="openstack_https_proxy")
def openstack_https_proxy_fixture(pytestconfig: pytest.Config) -> str:
    """Configured https_proxy setting for openstack runners."""
    https_proxy = pytestconfig.getoption("--openstack-https-proxy")
    return "" if https_proxy is None else https_proxy


@pytest.fixture(scope="module", name="openstack_no_proxy")
def openstack_no_proxy_fixture(pytestconfig: pytest.Config) -> str:
    """Configured no_proxy setting for openstack runners."""
    no_proxy = pytestconfig.getoption("--openstack-no-proxy")
    return "" if no_proxy is None else no_proxy


@pytest.fixture(scope="module")
def loop_device(pytestconfig: pytest.Config) -> Optional[str]:
    """Configured loop_device setting."""
    return pytestconfig.getoption("--loop-device")


@pytest.fixture(scope="module", name="private_endpoint_config")
def private_endpoint_config_fixture(pytestconfig: pytest.Config) -> PrivateEndpointConfigs | None:
    """The private endpoint configuration values."""
    auth_url = pytestconfig.getoption("--openstack-auth-url-amd64")
    password = pytestconfig.getoption("--openstack-password-amd64")
    project_domain_name = pytestconfig.getoption("--openstack-project-domain-name-amd64")
    project_name = pytestconfig.getoption("--openstack-project-name-amd64")
    user_domain_name = pytestconfig.getoption("--openstack-user-domain-name-amd64")
    user_name = pytestconfig.getoption("--openstack-username-amd64")
    region_name = pytestconfig.getoption("--openstack-region-name-amd64")
    if any(
        not val
        for val in (
            auth_url,
            password,
            project_domain_name,
            project_name,
            user_domain_name,
            user_name,
            region_name,
        )
    ):
        return None
    return {
        "auth_url": auth_url,
        "password": password,
        "project_domain_name": project_domain_name,
        "project_name": project_name,
        "user_domain_name": user_domain_name,
        "username": user_name,
        "region_name": region_name,
    }


@pytest.fixture(scope="module", name="private_endpoint_clouds_yaml")
def private_endpoint_clouds_yaml_fixture(
    private_endpoint_config: PrivateEndpointConfigs | None,
) -> Optional[str]:
    """The openstack private endpoint clouds yaml."""
    if not private_endpoint_config:
        return None
    return string.Template(
        Path("tests/integration/data/clouds.yaml.tmpl").read_text(encoding="utf-8")
    ).substitute(
        {
            "auth_url": private_endpoint_config["auth_url"],
            "password": private_endpoint_config["password"],
            "project_domain_name": private_endpoint_config["project_domain_name"],
            "project_name": private_endpoint_config["project_name"],
            "user_domain_name": private_endpoint_config["user_domain_name"],
            "username": private_endpoint_config["username"],
            "region_name": private_endpoint_config["region_name"],
        }
    )


@pytest.fixture(scope="module", name="clouds_yaml_contents")
def clouds_yaml_contents_fixture(
    openstack_clouds_yaml: Optional[str], private_endpoint_clouds_yaml: Optional[str]
):
    """The Openstack clouds yaml or private endpoint cloud yaml contents."""
    clouds_yaml_contents = openstack_clouds_yaml or private_endpoint_clouds_yaml
    assert clouds_yaml_contents, (
        "Please specify --openstack-clouds-yaml or all of private endpoint arguments "
        "(--openstack-auth-url, --openstack-password, --openstack-project-domain-name, "
        "--openstack-project-name, --openstack-user-domain-name, --openstack-user-name, "
        "--openstack-region-name)"
    )
    return clouds_yaml_contents


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture(pytestconfig: pytest.Config) -> str:
    """Network to use to spawn test instances under."""
    network_name = pytestconfig.getoption("--openstack-network-name-amd64")
    assert network_name, "Please specify the --openstack-network-name-amd64 command line option"
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture(pytestconfig: pytest.Config) -> str:
    """Flavor to create testing instances with."""
    flavor_name = pytestconfig.getoption("--openstack-flavor-name-amd64")
    assert flavor_name, "Please specify the --openstack-flavor-name command line option"
    return flavor_name


@pytest.fixture(scope="module", name="openstack_test_image")
def openstack_test_image_fixture(pytestconfig: pytest.Config) -> str:
    """Image for testing openstack interfaces."""
    test_image = pytestconfig.getoption("--openstack-test-image")
    assert test_image, "Please specify the --openstack-test-image command line option"
    return test_image


@pytest.fixture(scope="module", name="openstack_test_flavor")
def openstack_test_flavor_fixture(pytestconfig: pytest.Config) -> str:
    """Flavor for testing openstack interfaces."""
    test_flavor = pytestconfig.getoption("--openstack-test-flavor")
    assert test_flavor, "Please specify the --openstack-test-flavor command line option"
    return test_flavor


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(
    clouds_yaml_contents: str, app_name: str
) -> Generator[Connection, None, None]:
    """The openstack connection instance."""
    clouds_yaml = yaml.safe_load(clouds_yaml_contents)
    clouds_yaml_path = Path.cwd() / "clouds.yaml"
    clouds_yaml_path.write_text(data=clouds_yaml_contents, encoding="utf-8")
    first_cloud = next(iter(clouds_yaml["clouds"].keys()))
    with openstack.connect(first_cloud) as connection:
        yield connection

    # servers, keys, security groups, security rules, images are created by the charm.
    # don't remove security groups & rules since they are single instances.
    # don't remove images since it will be moved to image-builder
    for server in connection.list_servers():
        server_name: str = server.name
        if server_name.startswith(app_name):
            connection.delete_server(server_name)
    for key in connection.list_keypairs():
        key_name: str = key.name
        if key_name.startswith(app_name):
            connection.delete_keypair(key_name)


@pytest.fixture(scope="module")
def model(ops_test: OpsTest) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None
    return ops_test.model


@pytest.fixture(scope="module")
def runner_manager_github_client(token: str) -> GithubClient:
    return GithubClient(token=token)


@pytest_asyncio.fixture(scope="module")
async def app_no_runner(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
    existing_app: Optional[str],
) -> AsyncIterator[Application]:
    """Application with no runner."""
    if existing_app:
        application = model.applications[existing_app]
    else:
        # Set the scheduled event to 1 hour to avoid interfering with the tests.
        application = await deploy_github_runner_charm(
            model=model,
            charm_file=charm_file,
            app_name=app_name,
            path=path,
            token=token,
            runner_storage="memory",
            http_proxy=http_proxy,
            https_proxy=https_proxy,
            no_proxy=no_proxy,
            reconcile_interval=60,
        )
    await model.wait_for_idle(apps=[application.name], status=ACTIVE)
    return application


@pytest_asyncio.fixture(scope="module", name="image_builder")
async def image_builder_fixture(
    model: Model, private_endpoint_config: PrivateEndpointConfigs | None,
    existing_app: Optional[str],
):
    """The image builder application for OpenStack runners."""
    if not private_endpoint_config:
        raise ValueError("Private endpoints are required for testing OpenStack runners.")
    if not existing_app:
        app = await model.deploy(
            "github-runner-image-builder",
            channel="latest/edge",
            revision=2,
            constraints="cores=2 mem=16G root-disk=20G virt-type=virtual-machine",
            config={
                "app-channel": "edge",
                "build-interval": "12",
                "revision-history-limit": "5",
                "openstack-auth-url": private_endpoint_config["auth_url"],
                # Bandit thinks this is a hardcoded password
                "openstack-password": private_endpoint_config["password"],  # nosec: B105
                "openstack-project-domain-name": private_endpoint_config["project_domain_name"],
                "openstack-project-name": private_endpoint_config["project_name"],
                "openstack-user-domain-name": private_endpoint_config["user_domain_name"],
                "openstack-user-name": private_endpoint_config["username"],
            },
        )
        await model.wait_for_idle(apps=[app.name], wait_for_active=True, timeout=15 * 60)
    else:
        app = model.applications["github-runner-image-builder"]
    return app


@pytest_asyncio.fixture(scope="module", name="app_openstack_runner")
async def app_openstack_runner_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    openstack_http_proxy: str,
    openstack_https_proxy: str,
    openstack_no_proxy: str,
    clouds_yaml_contents: str,
    network_name: str,
    flavor_name: str,
    existing_app: Optional[str],
    image_builder: Application,
) -> AsyncIterator[Application]:
    """Application launching VMs and no runners."""
    if existing_app:
        application = model.applications[existing_app]
    else:
        application = await deploy_github_runner_charm(
            model=model,
            charm_file=charm_file,
            app_name=app_name,
            path=path,
            token=token,
            runner_storage="juju-storage",
            http_proxy=openstack_http_proxy,
            https_proxy=openstack_https_proxy,
            no_proxy=openstack_no_proxy,
            reconcile_interval=60,
            constraints={
                "root-disk": 50 * 1024,
                "mem": 16 * 1024,
            },
            config={
                OPENSTACK_CLOUDS_YAML_CONFIG_NAME: clouds_yaml_contents,
                OPENSTACK_NETWORK_CONFIG_NAME: network_name,
                OPENSTACK_FLAVOR_CONFIG_NAME: flavor_name,
                USE_APROXY_CONFIG_NAME: "true",
                LABELS_CONFIG_NAME: app_name,
            },
            wait_idle=False,
            use_local_lxd=False,
        )
        await model.integrate(f"{image_builder.name}:image", f"{application.name}:image")
    await model.wait_for_idle(apps=[application.name], status=ACTIVE, timeout=90 * 60)

    return application


@pytest_asyncio.fixture(scope="module")
async def app_one_runner(model: Model, app_no_runner: Application) -> AsyncIterator[Application]:
    """Application with a single runner.

    Test should ensure it returns with the application in a good state and has
    one runner.
    """
    await ensure_charm_has_runner(app=app_no_runner, model=model)

    return app_no_runner


@pytest_asyncio.fixture(scope="module")
async def app_scheduled_events(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application with no token.

    Test should ensure it returns with the application having one runner.

    This fixture has to deploy a new application. The scheduled events are set
    to one hour in other application to avoid conflicting with the tests.
    Changes to the duration of scheduled interval only takes effect after the
    next trigger. Therefore, it would take a hour for the duration change to
    take effect.
    """
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=path,
        token=token,
        runner_storage="memory",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=8,
    )

    await application.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    await reconcile(app=application, model=model)

    return application


@pytest_asyncio.fixture(scope="module")
async def app_runner(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application to test runners."""
    # Use a different app_name so workflows can select runners from this deployment.
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=f"{app_name}-test",
        path=path,
        token=token,
        runner_storage="memory",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
    )
    return application


@pytest_asyncio.fixture(scope="module", name="app_no_wait")
async def app_no_wait_fixture(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Github runner charm application without waiting for active."""
    app: Application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=path,
        token=token,
        runner_storage="juju-storage",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
        wait_idle=False,
    )
    await app.set_config({VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    return app


@pytest_asyncio.fixture(scope="module", name="tmate_ssh_server_app")
async def tmate_ssh_server_app_fixture(
    model: Model, app_no_wait: Application
) -> AsyncIterator[Application]:
    """tmate-ssh-server charm application related to GitHub-Runner app charm."""
    tmate_app: Application = await model.deploy("tmate-ssh-server", channel="edge")
    await app_no_wait.relate("debug-ssh", f"{tmate_app.name}:debug-ssh")
    await model.wait_for_idle(apps=[tmate_app.name], status=ACTIVE, timeout=60 * 30)

    return tmate_app


@pytest_asyncio.fixture(scope="module", name="tmate_ssh_server_unit_ip")
async def tmate_ssh_server_unit_ip_fixture(
    model: Model,
    tmate_ssh_server_app: Application,
) -> bytes | str:
    """tmate-ssh-server charm unit ip."""
    status: FullStatus = await model.get_status([tmate_ssh_server_app.name])
    try:
        unit_status: UnitStatus = next(
            iter(status.applications[tmate_ssh_server_app.name].units.values())
        )
        assert unit_status.public_address, "Invalid unit address"
        return unit_status.public_address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest.fixture(scope="module")
def github_client(token: str) -> Github:
    """Returns the github client."""
    gh = Github(token)
    rate_limit = gh.get_rate_limit()
    logging.info("GitHub token rate limit: %s", rate_limit.core)
    return gh


@pytest.fixture(scope="module")
def github_repository(github_client: Github, path: str) -> Repository:
    """Returns client to the Github repository."""
    return github_client.get_repo(path)


@pytest.fixture(scope="module")
def forked_github_repository(
    github_repository: Repository,
) -> Iterator[Repository]:
    """Create a fork for a GitHub repository."""
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


@pytest_asyncio.fixture(scope="module")
async def app_juju_storage(
    model: Model,
    charm_file: str,
    app_name: str,
    path: str,
    token: str,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
) -> AsyncIterator[Application]:
    """Application with juju storage setup."""
    # Set the scheduled event to 1 hour to avoid interfering with the tests.
    application = await deploy_github_runner_charm(
        model=model,
        charm_file=charm_file,
        app_name=app_name,
        path=path,
        token=token,
        runner_storage="juju-storage",
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
    )
    return application


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
    model: Model,
    basic_app: Application,
    instance_type: InstanceType,
    existing_app: Optional[str],
) -> AsyncIterator[Application]:
    # OpenStack integration does not need the grafana agent to collect metric.
    if instance_type == InstanceType.LOCAL_LXD and not existing_app:
        grafana_agent = await model.deploy(
            "grafana-agent",
            application_name=f"grafana-agent-{basic_app.name}",
            channel="latest/edge",
        )
        await model.relate(f"{basic_app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
        await model.wait_for_idle(apps=[basic_app.name], status=ACTIVE)
        await model.wait_for_idle(apps=[grafana_agent.name])

    yield basic_app


@pytest_asyncio.fixture(scope="module", name="mongodb")
async def mongodb_fixture(model: Model, existing_app: str | None) -> Application:
    """Deploy MongoDB."""
    if not existing_app:
        mongodb = await model.deploy(MONGODB_APP_NAME, channel="6/edge")
        await model.wait_for_idle(apps=[MONGODB_APP_NAME], status=ACTIVE)
    else:
        mongodb = model.applications["mongodb"]
    return mongodb


@pytest_asyncio.fixture(scope="module", name="app_for_reactive")
async def app_for_reactive_fixture(
    model: Model,
    app_openstack_runner: Application,
    mongodb: Application,
    existing_app: Optional[str],
) -> Application:
    """Application for testing reactive."""
    if not existing_app:
        await model.relate(f"{app_openstack_runner.name}:mongodb", f"{mongodb.name}:database")

    await model.wait_for_idle(apps=[app_openstack_runner.name, mongodb.name], status=ACTIVE)

    return app_openstack_runner


@pytest_asyncio.fixture(scope="module", name="basic_app")
async def basic_app_fixture(
    request: pytest.FixtureRequest, instance_type: InstanceType
) -> Application:
    """Setup the charm with the basic configuration."""
    if instance_type == InstanceType.OPENSTACK:
        app = request.getfixturevalue("app_openstack_runner")
    else:
        app = request.getfixturevalue("app_no_runner")
    return app


@pytest_asyncio.fixture(scope="function", name="instance_helper")
async def instance_helper_fixture(
    request: pytest.FixtureRequest, instance_type: InstanceType
) -> InstanceHelper:
    """Instance helper fixture."""
    helper: InstanceHelper
    if instance_type == InstanceType.OPENSTACK:
        openstack_connection = request.getfixturevalue("openstack_connection")
        helper = OpenStackInstanceHelper(openstack_connection=openstack_connection)
    else:
        helper = LXDInstanceHelper()
    return helper
