# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for requesting repo policy compliance service."""

import logging
from urllib.parse import urljoin

import requests
import urllib3

logger = logging.getLogger(__name__)


# Disable pylint public method number check as this class can be extended in the future.
class RepoPolicyComplianceClient:  # pylint: disable=too-few-public-methods
    """Client for repo policy compliance service.

    Attributes:
        base_url: Base url to the repo policy compliance service.
        token: Charm token configured for the repo policy compliance service.
    """

    def __init__(self, url: str, charm_token: str) -> None:
        """Construct the RepoPolicyComplianceClient.

        Args:
            url: Base URL to the repo policy compliance service.
            charm_token: Charm token configured for the repo policy compliance service.
        """
        self._session = self._create_session()
        self.base_url = url
        self.token = charm_token

    def get_one_time_token(self) -> str:
        """Get a single-use token for repo policy compliance check.

        Raises:
            HTTPError: If there was an error getting one-time token from repo-policy-compliance \
                service.

        Returns:
            The one-time token to be used in a single request of repo policy compliance check.
        """
        url = urljoin(str(self.base_url), "one-time-token")
        try:
            response = self._session.get(url, headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            return response.content.decode("utf-8")
        except requests.HTTPError:
            logger.exception("Unable to get one time token from repo policy compliance service.")
            raise

    def _create_session(self) -> requests.Session:
        """Create a new requests session.

        Returns:
            A new requests session with retries and no proxy settings.
        """
        # The repo policy compliance service might be on localhost and should not have any proxies
        # setting configured. This can be changed in the future when we also rely on an
        # external service for LXD cloud.
        adapter = requests.adapters.HTTPAdapter(
            max_retries=urllib3.Retry(
                total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504]
            )
        )

        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.trust_env = False
        return session
