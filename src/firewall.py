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
    """

    ip_range: str

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
        try:
            ipaddress.IPv4Network(entry)
        except ValueError as exc:
            raise ValueError(f"incorrect firewall entry format: {entry}") from exc
        return cls(ip_range=entry)


class Firewall:  # pylint: disable=too-few-public-methods
    """Represent a firewall and provides methods to refresh its configuration."""

    _ACL_RULESET_NAME = "github"

    def __init__(self, network: str):
        """Initialize a new Firewall instance.

        Args:
            network: The LXD network name.
        """
        self._network = network

    def get_host_ip(self) -> str:
        """Get the host IP address for the corresponding LXD network.

        Returns:
            The host IP address.
        """
        address = execute_command(
            ["/snap/bin/lxc", "network", "get", self._network, "ipv4.address"]
        )
        return str(ipaddress.IPv4Interface(address.strip()).ip)

    def refresh_firewall(self, denylist: typing.List[FirewallEntry]):
        """Refresh the firewall configuration.

        Args:
            denylist: The list of FirewallEntry objects to allow.
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
        execute_command(
            [
                "/snap/bin/lxc",
                "network",
                "set",
                self._network,
                "security.acls.default.egress.action=allow",
            ]
        )
        acl_config = yaml.safe_load(
            execute_command(["/snap/bin/lxc", "network", "acl", "show", self._ACL_RULESET_NAME])
        )
        host_ip = self.get_host_ip()
        egress_rules = [
            {
                "action": "reject",
                "destination": host_ip,
                "destination_port": "0-8079,8081-65535",
                "protocol": "tcp",
                "state": "enabled",
            },
            {
                "action": "reject",
                "destination": host_ip,
                "protocol": "udp",
                "state": "enabled",
            },
            {
                "action": "reject",
                "destination": host_ip,
                "protocol": "icmp4",
                "state": "enabled",
            },
            {
                "action": "reject",
                "destination": "::/0",
                "state": "enabled",
            }
        ]
        egress_rules.extend(
            [
                {
                    "action": "reject",
                    "destination": entry.ip_range,
                    "state": "enabled",
                }
                for entry in denylist
            ]
        )
        acl_config["egress"] = egress_rules
        execute_command(
            ["lxc", "network", "acl", "edit", self._ACL_RULESET_NAME],
            input=json.dumps(acl_config).encode("ascii"),
        )
