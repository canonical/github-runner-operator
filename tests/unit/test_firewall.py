# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for firewall module."""

from ipaddress import IPv4Network

import pytest

from firewall import Firewall


@pytest.mark.parametrize(
    "domain_ranges, exclude_ranges, expected",
    [
        pytest.param([], [], [], id="empty domain[no exclude]"),
        pytest.param([], (IPv4Network("127.0.0.1/32")), [], id="empty domain[one ip exclude]"),
        pytest.param(
            [],
            [IPv4Network("127.0.0.1/32"), IPv4Network("127.0.0.2/32")],
            [],
            id="empty domain[multiple ips exclude]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.1/32")],
            [IPv4Network("127.0.0.2/32")],
            [IPv4Network("127.0.0.1/32")],
            id="single ip single exclude ip[no overlap]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.1/32")],
            [IPv4Network("127.0.0.1/32")],
            [],
            id="single ip single exclude ip[overlap]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30")],
            [IPv4Network("127.0.0.2/32")],
            [IPv4Network("127.0.0.0/31"), IPv4Network("127.0.0.3/32")],
            id="single domain single exclude ip[overlap single ip]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/28")],  # 127.0.0.0-14
            [IPv4Network("127.0.0.1/32"), IPv4Network("127.0.1.1/32")],
            [
                IPv4Network("127.0.0.0/32"),  # 127.0.0.0
                IPv4Network("127.0.0.2/31"),  # 127.0.0.2-3
                IPv4Network("127.0.0.4/30"),  # 127.0.0.4-7
                IPv4Network("127.0.0.8/29"),  # 127.0.0.8-14
            ],
            id="single domain multiple exclude ips[overlap partial ips]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30")],  # 127.0.0.0-3
            [
                IPv4Network("127.0.0.0/32"),
                IPv4Network("127.0.0.1/32"),
                IPv4Network("127.0.0.2/32"),
                IPv4Network("127.0.0.3/32"),
            ],
            [],
            id="single domain multiple exclude ips[overlap all ips]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30")],
            [IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.0.0/30")],
            id="single domain single exclude domain[no overlap]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/28")],  # 127.0.0.0-15
            [IPv4Network("127.0.0.0/30")],  # 127.0.0.0-4
            [
                IPv4Network("127.0.0.8/29"),  # 127.0.0.8-15
                IPv4Network("127.0.0.4/30"),  # 127.0.0.5-7
            ],
            id="single domain single exclude domain[overlap partial range]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30")],
            [IPv4Network("127.0.0.0/30")],
            [],
            id="single domain single exclude domain[overlap full range]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.2.0/30")],
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            id="multiple domain single exclude domain[no overlap]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/28"), IPv4Network("127.0.1.0/28")],
            [IPv4Network("127.0.0.0/30")],
            [
                IPv4Network("127.0.0.8/29"),  # 127.0.0.8-15
                IPv4Network("127.0.0.4/30"),  # 127.0.0.5-7
                IPv4Network("127.0.1.0/28"),
            ],
            id="multiple domain single exclude domain[partial overlap]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.0.0/30")],
            id="multiple domain single exclude domain[full overlap(equivalent network)]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.0.0/8")],
            [],
            id="multiple domain single exclude domain[full overlap(bigger network)]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.2.0/30"), IPv4Network("127.0.3.0/30")],
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            id="multiple domain multiple exclude domain[no overlaps]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/28"), IPv4Network("127.0.1.0/28")],
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [
                IPv4Network("127.0.0.4/30"),  # 127.0.0.5-7
                IPv4Network("127.0.0.8/29"),  # 127.0.0.8-15
                IPv4Network("127.0.1.4/30"),  # 127.0.1.5-7
                IPv4Network("127.0.1.8/29"),  # 127.0.1.8-15
            ],
            id="multiple domain multiple exclude domain[multiple partial overlaps]",
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [],
            id=(
                "multiple domain multiple exclude domain[multiple full "
                "overlaps(equivalent network)]"
            ),
        ),
        pytest.param(
            [IPv4Network("127.0.0.0/30"), IPv4Network("127.0.1.0/30")],
            [IPv4Network("127.0.0.0/8")],
            [],
            id="multiple domain multiple exclude domain[multiple full overlaps(bigger network)]",
        ),
    ],
)
def test__exclude_network(
    domain_ranges: list[IPv4Network],
    exclude_ranges: list[IPv4Network],
    expected: list[IPv4Network],
):
    """
    arrange: given domain networks and some IPs to exclude from the domains.
    act: when _exclude_network is called.
    assert: new ip networks are returned with excluded target IP ranges.
    """
    result = Firewall("test")._exclude_network(domain_ranges, exclude_ranges)
    assert all(net in result for net in expected) and all(
        net in expected for net in result
    ), f"Difference in networks found, expected: {expected}, got: {result}."
