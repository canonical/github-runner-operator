# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for Firewall."""
import typing

import pytest

from firewall import FirewallEntry

TESTING_FIREWALL_ENTRIES = (
    pytest.param("1.2.3.4:1-2", FirewallEntry(ip_range="1.2.3.4", port_range="1-2", is_udp=False)),
    pytest.param("1.2.3.4:1:udp", FirewallEntry(ip_range="1.2.3.4", port_range="1", is_udp=True)),
    pytest.param("1.2.3.4:99999", None),
    pytest.param(
        "10.0.0.0/8:11-22:udp",
        FirewallEntry(ip_range="10.0.0.0/8", port_range="11-22", is_udp=True),
    ),
    pytest.param("10.0.0.1/8:11-22:udp", None),
    pytest.param("a.b.c.d:123", None),
    pytest.param("", None),
    pytest.param("1.2.3.4/a", None),
)


@pytest.mark.parametrize("entry,expected_firewall_entry", TESTING_FIREWALL_ENTRIES)
def test_parse_firewall_entry(entry: str, expected_firewall_entry: typing.Optional[FirewallEntry]):
    try:
        firewall_entry = FirewallEntry.decode(entry)
        assert firewall_entry == expected_firewall_entry
    except ValueError:
        if expected_firewall_entry is not None:
            raise
