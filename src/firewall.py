# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The runner firewall manager."""
import dataclasses
import ipaddress
import typing

import jinja2

from utilities import execute_command


@dataclasses.dataclass
class FirewallEntry:
    """Represent an entry in the firewall.

    Attrs:
        ip_range: The IP address range using CIDR notation.
        port_range: The port range, in the form of 80-81 or just one port number like 8080.
        is_udp: True if the entry is only for UDP traffic, False if the entry is only for TCP.
    """

    ip_range: str
    port_range: str
    is_udp: bool

    @classmethod
    def decode(cls, entry: str) -> "FirewallEntry":
        """Decode a firewall entry from a string.

        Args:
            entry: The firewall entry string, e.g. '192.168.0.1:80' or '192.168.0.0/24:80-90:udp'.

        Returns:
            FirewallEntry: A FirewallEntry instance representing the decoded entry.

        Raises:
            ValueError: If the entry string is not in the expected format.
        """

        def raise_format_error():
            """Raise a ValueError with a custom error message."""
            raise ValueError(f"incorrect firewall entry format: {entry}")

        def check_valid_ipv4_cidr(network: str):
            """Check if the given string is a valid IPv4 network in CIDR notation."""
            try:
                ipaddress.IPv4Network(network)
            except ValueError:
                raise_format_error()

        def check_valid_port(port: str):
            """Check if the given string is a valid port number."""
            if not port.isdigit() or int(port) < 1 or int(port) > 65535:
                raise_format_error()

        parts = entry.split(":")
        if len(parts) > 3:
            raise_format_error()
        if len(parts) == 3 and parts[2] != "udp":
            raise_format_error()
        ip_range, port_range = parts[:2]
        is_udp = len(parts) == 3
        check_valid_ipv4_cidr(ip_range)
        if "-" in port_range:
            port_range_parts = port_range.split("-")
            if len(port_range_parts) != 2:
                raise_format_error()
            port_start, port_end = port_range_parts
            check_valid_port(port_start)
            check_valid_port(port_end)
        else:
            check_valid_port(port_range)
        return cls(ip_range=ip_range, port_range=port_range, is_udp=is_udp)


class Firewall:  # pylint: disable=too-few-public-methods
    """Represent a firewall and provides methods to refresh its configuration."""

    def __init__(self, host_ip: str):
        """Initialize a new Firewall instance.

        Args:
            host_ip: The IP address of the host.
        """
        self._environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"), autoescape=True, trim_blocks=True
        )
        self._template = self._environment.get_template("github-runner-firewall.j2")
        self._host_ip = host_ip

    def _render_firewall_template(self, allowlist: typing.List[FirewallEntry]) -> str:
        """Render the firewall template with the provided allowlist.

        Args:
            allowlist: The list of FirewallEntry objects to allow.

        Returns:
            str: The rendered firewall template as a string.
        """
        return self._template.render(allowlist=allowlist, host_ip=self._host_ip)

    def refresh_firewall(self, allowlist: typing.List[FirewallEntry]):
        """Refresh the firewall configuration.

        Args:
            allowlist: The list of FirewallEntry objects to allow.
        """
        execute_command(
            ["/usr/sbin/nft", "-f", "-"],
            input=self._render_firewall_template(allowlist).encode("ascii"),
        )

    @classmethod
    def for_network(cls, lxc_network: str = "lxdbr0") -> "Firewall":
        """Create a firewall manager instance based on given lxc network.

        Args:
            lxc_network: The target lxc network name.
        """
        network = execute_command(["/snap/bin/lxc", "network", "get", lxc_network, "ipv4.address"])
        host_ip = str(ipaddress.IPv4Interface(network).ip)
        return cls(host_ip=host_ip)
