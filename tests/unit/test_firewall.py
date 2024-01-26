# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for firewall module."""

from ipaddress import IPv4Network

import pytest

from firewall import Firewall


@pytest.mark.parametrize(
    "domain_ranges, excludes_ranges, expected",
    [
        pytest.param(
            [IPv4Network("10.0.0.0/8")],
            [IPv4Network("10.136.12.36/32")],
            {
                IPv4Network("10.0.0.0/9"),
                IPv4Network("10.192.0.0/10"),
                IPv4Network("10.160.0.0/11"),
                IPv4Network("10.144.0.0/12"),
                IPv4Network("10.128.0.0/13"),
                IPv4Network("10.140.0.0/14"),
                IPv4Network("10.138.0.0/15"),
                IPv4Network("10.137.0.0/16"),
                IPv4Network("10.136.128.0/17"),
                IPv4Network("10.136.64.0/18"),
                IPv4Network("10.136.32.0/19"),
                IPv4Network("10.136.16.0/20"),
                IPv4Network("10.136.0.0/21"),
                IPv4Network("10.136.8.0/22"),
                IPv4Network("10.136.14.0/23"),
                IPv4Network("10.136.13.0/24"),
                IPv4Network("10.136.12.128/25"),
                IPv4Network("10.136.12.64/26"),
                IPv4Network("10.136.12.0/27"),
                IPv4Network("10.136.12.48/28"),
                IPv4Network("10.136.12.40/29"),
                IPv4Network("10.136.12.32/30"),
                IPv4Network("10.136.12.38/31"),
                IPv4Network("10.136.12.37/32"),
            },
            id="exclude a single IP",
        ),
        pytest.param(
            [IPv4Network("10.0.0.0/8"), IPv4Network("192.0.2.0/28")],
            [IPv4Network("10.136.12.36/32")],
            {
                IPv4Network("10.0.0.0/9"),
                IPv4Network("10.192.0.0/10"),
                IPv4Network("10.160.0.0/11"),
                IPv4Network("10.144.0.0/12"),
                IPv4Network("10.128.0.0/13"),
                IPv4Network("10.140.0.0/14"),
                IPv4Network("10.138.0.0/15"),
                IPv4Network("10.137.0.0/16"),
                IPv4Network("10.136.128.0/17"),
                IPv4Network("10.136.64.0/18"),
                IPv4Network("10.136.32.0/19"),
                IPv4Network("10.136.16.0/20"),
                IPv4Network("10.136.0.0/21"),
                IPv4Network("10.136.8.0/22"),
                IPv4Network("10.136.14.0/23"),
                IPv4Network("10.136.13.0/24"),
                IPv4Network("10.136.12.128/25"),
                IPv4Network("10.136.12.64/26"),
                IPv4Network("10.136.12.0/27"),
                IPv4Network("10.136.12.48/28"),
                IPv4Network("10.136.12.40/29"),
                IPv4Network("10.136.12.32/30"),
                IPv4Network("10.136.12.38/31"),
                IPv4Network("10.136.12.37/32"),
                IPv4Network("192.0.2.0/28"),
            },
            id="exclude a single IP and one different subnet",
        ),
        pytest.param(
            [IPv4Network("198.18.0.0/15"), IPv4Network("172.16.0.0/12")],
            [IPv4Network("10.136.12.36/32")],
            {IPv4Network("198.18.0.0/15"), IPv4Network("172.16.0.0/12")},
            id="no matching networks",
        ),
    ],
)
def test__exclude_network(
    domain_ranges: list[IPv4Network],
    excludes_ranges: list[IPv4Network],
    expected: set[IPv4Network],
):
    """
    arrange: given domain networks and some IPs to exclude from the domains.
    act: when _exclude_network is called.
    assert: new ip networks are returned with excluded target IP ranges.
    """
    assert Firewall("test")._exclude_network(domain_ranges, excludes_ranges) == expected
