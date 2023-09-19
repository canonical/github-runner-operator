#  Copyright 2023 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Functions for operating Promtail."""
import gzip
import logging
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Optional

import jinja2
import requests
from charms.loki_k8s.v0.loki_push_api import PROMTAIL_BASE_URL

from charm_state import ProxyConfig
from utilities import execute_command

SYSTEMCTL_PATH_STR = "/usr/bin/systemctl"

PROMTAIL_BINARY_PATH = Path("/usr/local/bin/promtail-linux-amd64")
PROMTAIL_BINARY_SHA_PATH = Path("/usr/local/bin/promtail-linux-amd64.sha256")
PROMTAIL_CONFIG_PATH = Path("/etc/promtail.yaml")
JINJA2_TEMPLATE_PATH = "templates"
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system/promtail.service")


logger = logging.getLogger(__name__)


class PromtailInstallationError(Exception):
    """Represents an error during installation of Promtail."""

    def __init__(self, msg: str):
        """Initialize a new instance of the PromtailInstallationError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


@dataclass
class PromtailDownloadInfo:
    """Information about the Promtail download.

    Attrs:
        url: The URL to download Promtail from.
        zip_sha256: The SHA256 hash of the Promtail zip file.
        bin_sha256: The SHA256 hash of the Promtail binary.
    """

    url: str
    zip_sha256: str
    bin_sha256: str


@dataclass
class Config:
    """Configuration options for Promtail.

    Attrs:
        loki_endpoint: The Loki endpoint to send logs to.
        proxies: Proxy settings.
        promtail_download_info: Information about the Promtail download.
    """

    loki_endpoint: str
    proxies: Optional[ProxyConfig]
    promtail_download_info: PromtailDownloadInfo


def _is_installed(promtail_download_info: PromtailDownloadInfo) -> bool:
    """Check if Promtail is installed."""
    return (
        # pflake8 complains about the line break before the binary operator
        # but this is how black formats it.
        PROMTAIL_BINARY_PATH.exists()
        and PROMTAIL_BINARY_SHA_PATH.exists()  # noqa: W503
        and PROMTAIL_BINARY_SHA_PATH.read_text(encoding="utf-8")  # noqa: W503
        == promtail_download_info.bin_sha256  # noqa: W503
    )


def _sha256sums_matches(file_path: Path, sha256sum: str) -> bool:
    """Check whether a file's sha256sum matches or not with a specific sha256sum.

    Args:
        file_path: The path to the file to check.
        sha256sum: The sha256sum against which we want to verify.

    Returns:
        a boolean representing whether a file's sha256sum matches or not with
        a specific sha256sum.
    """
    try:
        file_bytes = file_path.read_bytes()
        result = sha256(file_bytes).hexdigest()

        if result != sha256sum:
            logger.debug(
                "File sha256sum mismatch, expected:'%s{sha256sum}' but got '%s'",
                sha256sum,
                result,
            )
            return False
        return True
    except FileNotFoundError:
        logger.error("File: '%s' could not be opened", file_path)
        return False


def _install(promtail_download_info: PromtailDownloadInfo) -> None:
    if not promtail_download_info.url.startswith(PROMTAIL_BASE_URL):
        raise PromtailInstallationError(
            f"Unknown Promtail download URL {promtail_download_info.url}. "
            f"Must start with {PROMTAIL_BASE_URL}"
        )
    response = requests.get(promtail_download_info.url, timeout=300)
    response.raise_for_status()

    with open(PROMTAIL_BINARY_PATH.with_suffix(".gz"), "wb") as file:
        logger.info("Writing Promtail binary zip to %s", PROMTAIL_BINARY_PATH.with_suffix(".gz"))
        file.write(response.content)
    if not _sha256sums_matches(
        PROMTAIL_BINARY_PATH.with_suffix(".gz"), promtail_download_info.zip_sha256
    ):
        raise PromtailInstallationError(
            f"Promtail zip file sha256sum mismatch, expected: {promtail_download_info.zip_sha256}"
        )
    with gzip.open(PROMTAIL_BINARY_PATH.with_suffix(".gz"), "rb") as file:
        logger.info("Writing Promtail binary to %s", PROMTAIL_BINARY_PATH)
        PROMTAIL_BINARY_PATH.write_bytes(file.read())
        PROMTAIL_BINARY_PATH.chmod(0o551)
        if not _sha256sums_matches(PROMTAIL_BINARY_PATH, promtail_download_info.bin_sha256):
            try:
                PROMTAIL_BINARY_PATH.unlink()
            finally:
                raise PromtailInstallationError(
                    f"Promtail binary file sha256sum mismatch, expected: "
                    f"{promtail_download_info.zip_sha256}"
                )
        PROMTAIL_BINARY_SHA_PATH.write_text(promtail_download_info.bin_sha256, encoding="utf-8")


def _config(promtail_config: Config, environment: jinja2.Environment) -> None:
    config_str = environment.get_template("promtail.yaml.j2").render(
        loki_endpoint=promtail_config.loki_endpoint
    )
    PROMTAIL_CONFIG_PATH.write_text(config_str, encoding="utf-8")


def _start(config: Config, environment: jinja2.Environment) -> None:
    systemd_service = environment.get_template("promtail.service.j2").render(
        proxies=config.proxies
    )
    SYSTEMD_SERVICE_PATH.write_text(systemd_service, encoding="utf-8")
    execute_command([SYSTEMCTL_PATH_STR, "daemon-reload"], check_exit=True)
    execute_command([SYSTEMCTL_PATH_STR, "restart", "promtail"], check_exit=True)
    execute_command([SYSTEMCTL_PATH_STR, "enable", "promtail"], check_exit=True)


def start(config: Config) -> None:
    """Start Promtail.

    If Promtail has not already been installed, it will be installed
    and configured to send logs to Loki.
    If Promtail is already running, it will be reconfigured and restarted.

    Args:
        config: The configuration for Promtail.
    """
    if not _is_installed(config.promtail_download_info):
        logger.info("Installing Promtail")
        _install(config.promtail_download_info)
    else:
        logger.info("Promtail already installed, skipping installation")

    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(JINJA2_TEMPLATE_PATH), autoescape=True
    )

    _config(config, environment)

    _start(config, environment)


def restart() -> None:
    """Restart Promtail."""
    execute_command([SYSTEMCTL_PATH_STR, "restart", "promtail"], check_exit=True)


def stop() -> None:
    """Stop Promtail."""
    execute_command([SYSTEMCTL_PATH_STR, "stop", "promtail"], check_exit=True)


def is_running() -> bool:
    """Check if Promtail is running.

    Returns:
        True if Promtail is running, False otherwise.
    """
    _, code = execute_command(
        [SYSTEMCTL_PATH_STR, "is-active", "--quiet", "promtail"], check_exit=False
    )

    return code == 0
