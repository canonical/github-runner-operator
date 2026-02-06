# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""HTTP client utilities for consistent requests session setup."""

from __future__ import annotations

import requests


def configure_session(adapter: requests.adapters.HTTPAdapter) -> requests.Session:
    """Return a requests session with the provided adapter mounted and proxies disabled.

    This standardizes how we create sessions across clients by mounting the same adapter
    on both HTTP and HTTPS and ensuring environment proxy variables are ignored.

    Args:
        adapter: A configured `HTTPAdapter` with retry policy.

    Returns:
        A configured `requests.Session` instance.
    """
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.trust_env = False
    return session
