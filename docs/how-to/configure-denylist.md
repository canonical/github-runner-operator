# How to restrict self-hosted runner network access

The [`denylist` configuration](https://charmhub.io/github-runner/configure#denylist) can be used to restrict network access for self-hosted runners.

This can be employed to prevent self-hosted runners from accessing the network on the Juju machine. Generally, all IPv4 local addresses should be included in the denylist:

- 0.0.0.0/8
- 10.0.0.0/8
- 100.64.0.0/10
- 127.0.0.0/8
- 169.254.0.0/16
- 172.16.0.0/12
- 192.0.0.0/24
- 192.0.2.0/24
- 192.88.99.0/24
- 192.168.0.0/16
- 198.18.0.0/15
- 198.51.100.0/24
- 203.0.113.0/24
- 224.0.0.0/4
- 233.252.0.0/24
- 240.0.0.0/4

Additionally, include any IPv4 address or CIDR block that the runner should not have access to on the denylist.