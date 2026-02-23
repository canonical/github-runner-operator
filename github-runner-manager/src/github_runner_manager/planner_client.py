# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client to interact with the planner service."""

import json
import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
import requests.adapters
import urllib3
from pydantic import AnyHttpUrl, BaseModel

logger = logging.getLogger(__name__)


@dataclass
class PressureInfo:
    """Pressure information for a flavor returned by the planner service.

    Attributes:
        pressure: Desired total runner count for the flavor.
    """

    pressure: int


class PlannerConfiguration(BaseModel):
    """Configuration inputs for the PlannerClient.

    Attributes:
        base_url: Base URL of the planner service.
        token: Bearer token used to authenticate against the planner service.
        timeout: Default timeout in seconds for HTTP requests.
    """

    base_url: AnyHttpUrl
    token: str
    timeout: int = 5 * 60


class PlannerApiError(Exception):
    """Represents an error while interacting with the planner service."""


class PlannerClient:  # pylint: disable=too-few-public-methods
    """An HTTP client for the planner service."""

    def __init__(self, config: PlannerConfiguration) -> None:
        """Initialize client with planner configuration.

        Args:
            config: Planner service configuration containing base URL,
                authentication token, and default request timeout.
        """
        self._session = self._create_session()
        self._config = config

    def stream_pressure(self, name: str) -> Iterable[PressureInfo]:
        """Stream pressure updates for the given flavor.

        Args:
            name: Flavor name.

        Yields:
            Parsed pressure updates.

        Raises:
            PlannerApiError: On HTTP or stream errors.
        """
        url = urljoin(str(self._config.base_url), f"/api/v1/flavors/{name}/pressure?stream=true")
        try:
            with self._session.get(
                url,
                headers={"Authorization": f"Bearer {self._config.token}"},
                timeout=self._config.timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # The planner sends periodic heartbeat pings as non-dict values.
                        if not isinstance(data, dict) or "pressure" not in data:
                            logger.debug("Skipping non-pressure stream line: %s", line)
                            continue
                        yield PressureInfo(pressure=int(data[name]))
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed stream line: %s", line)
                        continue
        except requests.RequestException as exc:
            logger.exception("Error while streaming pressure for flavor '%s' from planner.", name)
            raise PlannerApiError from exc

    @staticmethod
    def _create_session() -> requests.Session:
        """Create a requests session with retries and no env proxies.

        Returns:
            A configured `requests.Session` instance.
        """
        adapter = requests.adapters.HTTPAdapter(
            max_retries=urllib3.Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504],
            )
        )

        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
