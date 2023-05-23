# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class RepoPolicyComplianceClient:
    def __init__(self, session: requests.Session, url: str, charm_token: str):
        self.session = session
        self.base_url = url
        self.token = charm_token

    def get_one_time_token(self) -> str:
        url = urljoin(self.base_url, "one-time-token")
        try:
            response = self.session.get(url, headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            return response.content
        except requests.HTTPError:
            logger.exception("Unable to get one time token from repo policy compliance service.")
            raise
