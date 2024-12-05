# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The runner firewall manager."""
import dataclasses
import ipaddress


@dataclasses.dataclass
class FirewallEntry:
    """Represent an entry in the firewall.

    Attributes:
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
