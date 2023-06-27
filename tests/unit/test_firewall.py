# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test cases for Firewall."""
import textwrap
import typing

import pytest

from firewall import Firewall, FirewallEntry

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


@pytest.mark.parametrize("entry,excepted_firewall_entry", TESTING_FIREWALL_ENTRIES)
def test_parse_firewall_entry(entry: str, excepted_firewall_entry: typing.Optional[FirewallEntry]):
    try:
        firewall_entry = FirewallEntry.decode(entry)
        assert firewall_entry == excepted_firewall_entry
    except ValueError:
        if excepted_firewall_entry is not None:
            raise


def test_default_firewall_ruleset():
    firewall = Firewall("10.98.139.1")
    allowlist = [
        FirewallEntry.decode("0.0.0.0/0:1-65535"),
        FirewallEntry.decode("0.0.0.0/0:1-65535:udp"),
    ]

    ruleset = firewall._render_firewall_template(allowlist)
    excepted = textwrap.dedent(
        """\
    table bridge github_runner_firewall
    delete table bridge github_runner_firewall

    table bridge github_runner_firewall {
        chain github_runner_firewall_prerouting {
            type filter hook prerouting priority 0; policy accept;

            ether type arp accept
            ct state established,related accept

            iifname "tap*" ip daddr 10.98.139.1 udp dport 53 counter accept
            iifname "tap*" ip daddr { 10.98.139.1, 255.255.255.255 } udp dport 67 counter accept
            iifname "tap*" ip daddr 10.98.139.1 tcp dport 8080 counter accept

            iifname "tap*" ip daddr 0.0.0.0/0 tcp dport 1-65535 counter accept
            iifname "tap*" ip daddr 0.0.0.0/0 udp dport 1-65535 counter accept

            iifname "tap*" counter reject with icmpx type admin-prohibited
        }
    }"""
    )
    assert excepted == ruleset
