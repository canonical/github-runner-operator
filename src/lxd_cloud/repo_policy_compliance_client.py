# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Client for requesting repo policy compliance service."""

import logging
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


# Disable pylint public method number check as this class can be extended in the future.
class RepoPolicyComplianceClient:  # pylint: disable=too-few-public-methods
    """Client for repo policy compliance service.

    Attributes:
        base_url: Base url to the repo policy compliance service.
        token: Charm token configured for the repo policy compliance service.
    """

    def __init__(self, session: requests.Session, url: str, charm_token: str) -> None:
        """Construct the RepoPolicyComplianceClient.

        Args:
            session: The request Session object for making HTTP requests.
            url: Base URL to the repo policy compliance service.
            charm_token: Charm token configured for the repo policy compliance service.
        """
        self._session = session
        self.base_url = url
        self.token = charm_token

    def get_one_time_token(self) -> str:
        """Get a single-use token for repo policy compliance check.

        Returns:
            The one-time token to be used in a single request of repo policy compliance check.
        """
        url = urljoin(self.base_url, "one-time-token")
        try:
            response = self._session.get(url, headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            return response.content.decode("utf-8")
        except requests.HTTPError:
            logger.exception("Unable to get one time token from repo policy compliance service.")
            raise
