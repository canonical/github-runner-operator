# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import logging
import os
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
from github_runner_manager.github_client import GithubClient
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Model
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

from charm_state import (
    BASE_VIRTUAL_MACHINES_CONFIG_NAME,
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
    reconcile,
    wait_for,
)
from tests.integration.helpers.openstack import OpenStackInstanceHelper, PrivateEndpointConfigs
from tests.status_name import ACTIVE

IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS = 30 * 60

# The following line is required because we are using request.getfixturevalue in conjunction
# with pytest-asyncio. See https://github.com/pytest-dev/pytest-asyncio/issues/112
nest_asyncio.apply()


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


@pytest.fixture(scope="module", name="openstack_clouds_yaml")
def openstack_clouds_yaml_fixture(pytestconfig: pytest.Config) -> str | None:
    """The openstack clouds yaml config."""
    return pytestconfig.getoption("--openstack-clouds-yaml")


@pytest.fixture(scope="module")
def charm_file(pytestconfig: pytest.Config, openstack_clouds_yaml: Optional[str]) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "Please specify the --charm-file command line option"
    charm_path_str = f"./{charm}"

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
    token = pytestconfig.getoption("--token") or os.environ.get("INTEGRATION_TOKEN")
    assert token, "Please specify the --token command line option"
    tokens = {token.strip() for token in token.split(",")}
    random_token = random.choice(list(tokens))
    return random_token


@pytest.fixture(scope="module")
def token_alt(pytestconfig: pytest.Config, token: str) -> str:
    """Configured token_alt setting."""
    token_alt = pytestconfig.getoption("--token-alt") or os.environ.get("INTEGRATION_TOKEN_ALT")
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


@pytest.fixture(scope="module", name="private_endpoint_config")
def private_endpoint_config_fixture(pytestconfig: pytest.Config) -> PrivateEndpointConfigs | None:
    """The private endpoint configuration values."""
    auth_url = pytestconfig.getoption("--openstack-auth-url-amd64")
    password = pytestconfig.getoption("--openstack-password-amd64")
    password = password or os.environ.get("INTEGRATION_OPENSTACK_PASSWORD_AMD64")
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
    basic_app: Application,
) -> AsyncIterator[Application]:
    """Application with no runner."""
    await basic_app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await model.wait_for_idle(apps=[basic_app.name], status=ACTIVE, timeout=20 * 60)
    yield basic_app


@pytest_asyncio.fixture(scope="module")
async def openstack_model_proxy(
    openstack_http_proxy: str,
    openstack_https_proxy: str,
    openstack_no_proxy: str,
    model: Model,
) -> None:
    await model.set_config(
        {
            "juju-http-proxy": openstack_http_proxy,
            "juju-https-proxy": openstack_https_proxy,
            "juju-no-proxy": openstack_no_proxy,
            "logging-config": "<root>=INFO;unit=INFO",
        }
    )


@pytest_asyncio.fixture(scope="module", name="image_builder_config")
async def image_builder_config_fixture(
    private_endpoint_config: PrivateEndpointConfigs | None,
    flavor_name: str,
    network_name: str,
):
    """The image builder application default for OpenStack runners."""
    if not private_endpoint_config:
        raise ValueError("Private endpoints are required for testing OpenStack runners.")
    return {
        "build-interval": "12",
        "revision-history-limit": "2",
        "openstack-auth-url": private_endpoint_config["auth_url"],
        # Bandit thinks this is a hardcoded password
        "openstack-password": private_endpoint_config["password"],  # nosec: B105
        "openstack-project-domain-name": private_endpoint_config["project_domain_name"],
        "openstack-project-name": private_endpoint_config["project_name"],
        "openstack-user-domain-name": private_endpoint_config["user_domain_name"],
        "openstack-user-name": private_endpoint_config["username"],
        "build-flavor": flavor_name,
        "build-network": network_name,
        "architecture": "amd64",
    }


@pytest_asyncio.fixture(scope="module", name="image_builder")
async def image_builder_fixture(
    model: Model,
    existing_app_suffix: Optional[str],
    image_builder_app_name: str,
    image_builder_config: dict,
    flavor_name: str,
    network_name: str,
    openstack_model_proxy: None,
    openstack_connection,
):
    """The image builder application for OpenStack runners."""
    if not existing_app_suffix:
        application_name = image_builder_app_name
        app = await model.deploy(
            "github-runner-image-builder",
            application_name=application_name,
            channel="latest/edge",
            revision=68,
            config=image_builder_config,
        )
    else:
        app = model.applications[image_builder_app_name]
    yield app
    # The github-image-builder does not clean keypairs. Until it does,
    # we clean them manually here.
    for key in openstack_connection.list_keypairs():
        key_name: str = key.name
        if key_name.startswith(image_builder_app_name):
            openstack_connection.delete_keypair(key_name)


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
    existing_app_suffix: Optional[str],
    image_builder: Application,
) -> AsyncIterator[Application]:
    """Application launching VMs and no runners."""
    if existing_app_suffix:
        application = model.applications[app_name]
    else:
        application = await deploy_github_runner_charm(
            model=model,
            charm_file=charm_file,
            app_name=app_name,
            path=path,
            token=token,
            http_proxy=openstack_http_proxy,
            https_proxy=openstack_https_proxy,
            no_proxy=openstack_no_proxy,
            reconcile_interval=60,
            constraints={
                "root-disk": 50 * 1024,
                "mem": 2 * 1024,
            },
            config={
                OPENSTACK_CLOUDS_YAML_CONFIG_NAME: clouds_yaml_contents,
                OPENSTACK_NETWORK_CONFIG_NAME: network_name,
                OPENSTACK_FLAVOR_CONFIG_NAME: flavor_name,
                USE_APROXY_CONFIG_NAME: "true",
                LABELS_CONFIG_NAME: app_name,
            },
            wait_idle=False,
        )
        await model.integrate(f"{image_builder.name}:image", f"{application.name}:image")
    await model.wait_for_idle(
        apps=[application.name, image_builder.name],
        status=ACTIVE,
        timeout=IMAGE_BUILDER_INTEGRATION_TIMEOUT_IN_SECONDS,
    )

    return application


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
    await reconcile(app=application, model=model)
    return application


@pytest_asyncio.fixture(scope="module", name="app_no_wait_tmate")
async def app_no_wait_tmate_fixture(
    model: Model,
    app_openstack_runner,
):
    """Application to check tmate ssh with openstack without waiting for active."""
    application = app_openstack_runner
    await application.set_config(
        {"reconcile-interval": "60", BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"}
    )
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
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        no_proxy=no_proxy,
        reconcile_interval=60,
        wait_idle=False,
    )
    await app.set_config({BASE_VIRTUAL_MACHINES_CONFIG_NAME: "1"})
    return app


@pytest_asyncio.fixture(scope="module", name="tmate_ssh_server_app")
async def tmate_ssh_server_app_fixture(
    model: Model, app_no_wait_tmate: Application
) -> AsyncIterator[Application]:
    """tmate-ssh-server charm application related to GitHub-Runner app charm."""
    tmate_app: Application = await model.deploy("tmate-ssh-server", channel="edge")
    await app_no_wait_tmate.relate("debug-ssh", f"{tmate_app.name}:debug-ssh")
    await model.wait_for_idle(apps=[tmate_app.name], status=ACTIVE, timeout=60 * 30)

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
        mongodb = await model.deploy(MONGODB_APP_NAME, channel="6/edge")
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
