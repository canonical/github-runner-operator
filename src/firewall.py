# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The runner firewall manager."""
import dataclasses
import ipaddress
import json
import typing

import yaml

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

    _ACL_RULESET_NAME = "github"

    def __init__(self, network: str):
        """Initialize a new Firewall instance.

        Args:
            network: The LXD network name.
        """
        self._network = network

    def _get_host_ip(self) -> str:
        """Get the host IP address for the corresponding LXD network.

        Returns:
            The host IP address.
        """
        address = execute_command(
            ["/snap/bin/lxc", "network", "get", self._network, "ipv4.address"]
        )
        return str(ipaddress.IPv4Interface(address.strip()).ip)

    def refresh_firewall(self, allowlist: typing.List[FirewallEntry]):
        """Refresh the firewall configuration.

        Args:
            allowlist: The list of FirewallEntry objects to allow.
        """
        current_acls = [
            acl["name"]
            for acl in yaml.safe_load(
                execute_command(["lxc", "network", "acl", "list", "-f", "yaml"])
            )
        ]
        if self._ACL_RULESET_NAME not in current_acls:
            execute_command(["/snap/bin/lxc", "network", "acl", "create", self._ACL_RULESET_NAME])
        execute_command(
            [
                "/snap/bin/lxc",
                "network",
                "set",
                self._network,
                f"security.acls={self._ACL_RULESET_NAME}",
            ]
        )
        acl_config = yaml.safe_load(
            execute_command(["/snap/bin/lxc", "network", "acl", "show", self._ACL_RULESET_NAME])
        )
        acl_config["egress"] = [
            {
                "action": "allow",
                "destination": entry.ip_range,
                "protocol": "udp" if entry.is_udp else "tcp",
                "destination_port": entry.port_range,
                "state": "enabled",
            }
            for entry in allowlist
        ]
        execute_command(
            ["lxc", "network", "acl", "edit", self._ACL_RULESET_NAME],
            input=json.dumps(acl_config).encode("ascii"),
        )
