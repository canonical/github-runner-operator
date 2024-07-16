# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

import pathlib
import typing


class ProxyConfig(typing.NamedTuple):
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
    """

    http: str
    https: str
    no_proxy: str


class CommonAppConfig(typing.NamedTuple):
    """Common application deploy config values.

    Attributes:
        app_name: The existing app name or "integration-id" prefixed random test id.
        charm_file: Path to charm file to use.
        path: The testing repo path.
        token: The testing GitHub token.
    """

    app_name: str
    charm_file: str | pathlib.Path
    path: str
    token: str
