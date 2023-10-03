#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

import secrets
from pathlib import Path
from unittest.mock import Mock

import jinja2
import pytest
from _pytest.monkeypatch import MonkeyPatch
from charms.loki_k8s.v0.loki_push_api import PROMTAIL_BASE_URL
from requests import HTTPError

import promtail
from errors import SubprocessError

TEST_PROMTAIL_ZIP = (
    b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\xcbH\xcd\xc9\xc9W(\xcf/\xcaI\xe1\x02"
    b"\x00-;\x08\xaf\x0c\x00\x00\x00"
)
TEST_PROMTAIL_BINARY = b"hello world\n"
TEST_PROMTAIL_ZIP_SHA256 = "691d5610f9f7c327facbf8856c5293c7a741b8ad2c4fa31775f3cca51c62e9dd"
TEST_PROMTAIL_BINARY_SHA256 = "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
TEST_DOWNLOAD_URL = f"{PROMTAIL_BASE_URL}/promtail-linux-amd64.gz"
TEST_PROMTAIL_DOWNLOAD_INFO = promtail.PromtailDownloadInfo(
    url=TEST_DOWNLOAD_URL,
    bin_sha256=TEST_PROMTAIL_BINARY_SHA256,
    zip_sha256=TEST_PROMTAIL_ZIP_SHA256,
)


@pytest.fixture(autouse=True, name="promtail_paths")
def promtail_paths_fixture(monkeypatch: MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """
    Mock the hardcoded promtail paths.
    """
    binary_path = tmp_path / "promtail-linux-amd64"
    monkeypatch.setattr("promtail.PROMTAIL_BINARY_PATH", binary_path)
    sha_path = binary_path.with_suffix(".sha256")
    monkeypatch.setattr("promtail.PROMTAIL_BINARY_SHA_PATH", sha_path)
    config_path = tmp_path / "promtail.yaml"
    monkeypatch.setattr("promtail.PROMTAIL_CONFIG_PATH", config_path)
    systemd_service_path = tmp_path / "systemd-service"
    monkeypatch.setattr("promtail.SYSTEMD_SERVICE_PATH", systemd_service_path)
    return {
        "binary": binary_path,
        "binary_sha256": sha_path,
        "config": config_path,
        "systemd_service": systemd_service_path,
    }


@pytest.fixture(autouse=True, name="jinja2_environment")
def jinja2_environment_fixture(monkeypatch: MonkeyPatch) -> jinja2.Environment:
    """
    Mock the jinja2 environment.
    """
    template_path = str(Path(__file__).parent / "../../templates")
    monkeypatch.setattr("promtail.JINJA2_TEMPLATE_PATH", template_path)
    return jinja2.Environment(loader=jinja2.FileSystemLoader(template_path), autoescape=True)


@pytest.fixture(autouse=True, name="exc_cmd_mock")
def exc_command_fixture(monkeypatch: MonkeyPatch) -> Mock:
    """Mock the execution of a command."""
    exc_cmd_mock = Mock()
    monkeypatch.setattr("promtail.execute_command", exc_cmd_mock)
    return exc_cmd_mock


@pytest.fixture(autouse=True, name="mock_download")
def mock_download_fixture(requests_mock):
    """Mock the download request to return the test binary."""
    requests_mock.get(TEST_DOWNLOAD_URL, content=TEST_PROMTAIL_ZIP)


def _call_promtail_setup():
    """Call promtail.setup with the test config."""
    promtail.setup(
        promtail.Config(
            loki_endpoint=secrets.token_hex(16),
            proxies=None,
            promtail_download_info=TEST_PROMTAIL_DOWNLOAD_INFO,
        )
    )


def test_setup_installs_promtail(promtail_paths: dict[str, Path]):
    """
    arrange: Mock requests and the binary path.
    act: Call setup.
    assert: The mocked promtail binary is installed in the expected location.
    """
    _call_promtail_setup()

    assert promtail_paths["binary"].read_bytes() == TEST_PROMTAIL_BINARY


def test_setup_does_not_install_promtail_if_already_installed(promtail_paths: dict[str, Path]):
    """
    arrange: Place a fake file with different content than the test binary in the binary path.
    act: Call setup.
    assert: The mocked promtail binary is not installed in the expected location.
    """
    promtail_paths["binary"].write_text("fake")
    promtail_paths["binary_sha256"].write_text(TEST_PROMTAIL_BINARY_SHA256)

    _call_promtail_setup()

    assert promtail_paths["binary"].read_text() == "fake"


def test_setup_reinstalls_promtail_if_sha_differs(promtail_paths: dict[str, Path]):
    """
    arrange: Place a fake promtail and a sha256 file with different content than the expected
        sha256 in the binary path.
    act: Call setup.
    assert: The mocked promtail binary is reinstalled in the expected location.
    """
    promtail_paths["binary"].write_text("fake")
    promtail_paths["binary_sha256"].write_text(TEST_PROMTAIL_BINARY_SHA256 + "fake")

    _call_promtail_setup()

    assert promtail_paths["binary"].read_bytes() == TEST_PROMTAIL_BINARY


def test_install_raises_requests_error(requests_mock):
    """
    arrange: Mock requests to raise a HTTPError.
    act: Call setup.
    assert: The expected exception is raised.
    """
    requests_mock.get(TEST_DOWNLOAD_URL, status_code=404)

    with pytest.raises(HTTPError):
        _call_promtail_setup()


def test_install_security_measurements(requests_mock):
    """
    arrange: Mock requests.
    act:
        1. Call setup with a different base url than expected.
        2. Call setup with a zip file that has a different hash than expected.
        3. Call setup with a binary file that has a different hash than expected.
    assert: PromtailInstallationError is raised in all cases.
    """

    # 1. different base url as expected
    promtail_download_info = promtail.PromtailDownloadInfo(
        url="https://www.example.com",
        bin_sha256=TEST_PROMTAIL_BINARY_SHA256,
        zip_sha256=TEST_PROMTAIL_ZIP_SHA256,
    )

    with pytest.raises(promtail.PromtailInstallationError):
        promtail.setup(
            promtail.Config(
                loki_endpoint=secrets.token_hex(16),
                proxies=None,
                promtail_download_info=promtail_download_info,
            )
        )

    # 2. zip has differing hash
    different_zip = (
        b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03K\xcb\xcfWHJ,"
        b"\xe2\x02\x00'\xb4\xdd\x13\x08\x00\x00\x00"
    )
    requests_mock.get(TEST_DOWNLOAD_URL, content=different_zip)
    with pytest.raises(promtail.PromtailInstallationError):
        _call_promtail_setup()

    # 3. binary has differing hash
    # we adapt the zip hash to match the different zip but make sure the binary hash is different
    different_zip_sha256 = "2054ec1d9c439c895f359314181704d6559d1e1ebc4ffc2e53b4be39f5be6ac2"
    requests_mock.get(TEST_DOWNLOAD_URL, content=different_zip)
    promtail_download_info = promtail.PromtailDownloadInfo(
        url=TEST_DOWNLOAD_URL,
        bin_sha256=TEST_PROMTAIL_BINARY_SHA256,
        zip_sha256=different_zip_sha256,
    )

    with pytest.raises(promtail.PromtailInstallationError):
        promtail.setup(
            promtail.Config(
                loki_endpoint=secrets.token_hex(16),
                proxies=None,
                promtail_download_info=promtail_download_info,
            )
        )


def test_install_writes_config_file(
    promtail_paths: dict[str, Path], jinja2_environment: jinja2.Environment
):
    """
    arrange: Mock the config location and jinja environment.
    act: Call config.
    assert: The expected configuration file has been created.
    """
    loki_endpoint = secrets.token_hex(16)
    promtail_config = promtail.Config(
        loki_endpoint=loki_endpoint,
        proxies=None,
        promtail_download_info=TEST_PROMTAIL_DOWNLOAD_INFO,
    )
    promtail.setup(promtail_config)

    assert promtail_paths["config"].read_text() == jinja2_environment.get_template(
        "promtail.yaml.j2"
    ).render(
        loki_endpoint=loki_endpoint,
    )


def test_setup_starts_a_systemd_service(
    promtail_paths: dict[str, Path], exc_cmd_mock: Mock, jinja2_environment: jinja2.Environment
):
    """
    arrange: Mock the systemd service file location and executions of execute_command.
    act: Call setup.
    assert: The systemd service file has been created and the expected command has been executed.
    """
    _call_promtail_setup()

    assert promtail_paths["systemd_service"].read_text() == jinja2_environment.get_template(
        "promtail.service.j2"
    ).render(proxies={})
    assert exc_cmd_mock.call_args_list == [
        ((([promtail.SYSTEMCTL_PATH_STR, "daemon-reload"]),), {"check_exit": True}),
        ((([promtail.SYSTEMCTL_PATH_STR, "restart", "promtail"]),), {"check_exit": True}),
        ((([promtail.SYSTEMCTL_PATH_STR, "enable", "promtail"]),), {"check_exit": True}),
    ]


def test_restart_restarts_systemd_service(exc_cmd_mock: Mock):
    """
    arrange: Mock executions of execute_command.
    act: Call restart.
    assert: The expected command has been executed.
    """
    promtail.restart()

    exc_cmd_mock.assert_called_with(
        [promtail.SYSTEMCTL_PATH_STR, "restart", "promtail"], check_exit=True
    )


def test_stop(exc_cmd_mock: Mock):
    """
    arrange: Mock the execution of execute_command.
    act: Call stop.
    assert: The expected command has been executed.
    """
    promtail.stop()

    exc_cmd_mock.assert_called_once_with(
        [promtail.SYSTEMCTL_PATH_STR, "stop", "promtail"], check_exit=True
    )


def test_is_running_returns_true_for_zero_exit_code(exc_cmd_mock: Mock):
    """
    arrange: Mock the execution of execute_command to return a zero exit code.
    act: Call is_running.
    assert: True is returned.
    """
    exc_cmd_mock.return_value = ("", 0)

    assert promtail.is_running()


def test_is_running_returns_false_for_non_zero_exit_code(exc_cmd_mock: Mock):
    """
    arrange: Mock the execution of execute_command to return a non-zero exit code.
    act: Call is_running.
    assert: False is returned.
    """
    exc_cmd_mock.return_value = ("", 1)

    assert not promtail.is_running()


@pytest.mark.parametrize(
    "promtail_fct",
    [
        (
            "setup",
            [
                promtail.Config(
                    loki_endpoint=secrets.token_hex(16),
                    proxies=None,
                    promtail_download_info=promtail.PromtailDownloadInfo(
                        url=TEST_DOWNLOAD_URL,
                        bin_sha256=TEST_PROMTAIL_BINARY_SHA256,
                        zip_sha256=TEST_PROMTAIL_ZIP_SHA256,
                    ),
                )
            ],
        ),
        ("restart", []),
        ("stop", []),
    ],
)
def test_promtail_fct_raises_error_for_non_successful_command(exc_cmd_mock, promtail_fct):
    """
    arrange: Mock the execution of execute_command to raise an error.
    act: Call promtail_fct
    assert: The expected exception is raised.
    """
    exc_cmd_mock.side_effect = SubprocessError("cmd", 1, "error", "error")

    with pytest.raises(SubprocessError):
        getattr(promtail, promtail_fct[0])(*promtail_fct[1])
