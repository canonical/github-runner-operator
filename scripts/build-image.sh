#!/usr/bin/env bash

set -e

/snap/bin/lxc launch ubuntu-daily:jammy runner --vm
while ! /snap/bin/lxc exec runner -- /usr/bin/who
do
    echo "Wait for lxd agent to be ready"
    sleep 10
done
while ! /snap/bin/lxc exec runner -- /usr/bin/nslookup github.com
do
    echo "Wait for network to be ready"
    sleep 10
done

/snap/bin/lxc exec runner -- /usr/bin/apt-get update
/snap/bin/lxc exec runner --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec runner --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install linux-generic-hwe-22.04 -yq

/snap/bin/lxc restart runner
while ! /snap/bin/lxc exec runner -- /usr/bin/who
do
    echo "Wait for lxd agent to be ready"
    sleep 10
done
while ! /snap/bin/lxc exec runner -- /usr/bin/nslookup github.com
do
    echo "Wait for network to be ready"
    sleep 10
done

/snap/bin/lxc exec runner -- /usr/bin/apt-get update
/snap/bin/lxc exec runner --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec runner --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install docker.io npm python3-pip shellcheck jq wget -yq
/snap/bin/lxc exec runner -- /usr/sbin/groupadd microk8s
/snap/bin/lxc exec runner -- /usr/sbin/usermod -aG microk8s ubuntu
/snap/bin/lxc exec runner -- /usr/sbin/usermod -aG docker ubuntu
/snap/bin/lxc exec runner -- /usr/sbin/iptables -I DOCKER-USER -j ACCEPT

# Set up aproxy for downloading
sudo /usr/bin/snap install aproxy --edge
sudo /usr/bin/snap set aproxy proxy=squid.internal:3128
sudo nft -f - << EOF
define default-ip = $(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \K\S+') | grep -oP 'src \K\S+')
define private-ips = { 10.0.0.0/8, 127.0.0.1/8, 172.16.0.0/12, 192.168.0.0/16 }
table ip aproxy
flush table ip aproxy
table ip aproxy {
      chain prerouting {
              type nat hook prerouting priority dstnat; policy accept;
              ip daddr != \$private-ips tcp dport { 80, 443 } counter dnat to \$default-ip:8443
      }

      chain output {
              type nat hook output priority -100; policy accept;
              ip daddr != \$private-ips tcp dport { 80, 443 } counter dnat to \$default-ip:8443
      }
}
EOF

# Download and verify checksum of yq
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh
/usr/bin/bash extract-checksum.sh SHA-256 yq_linux_amd64 | /usr/bin/awk '{print $2,$1}' | /usr/bin/sha256sum -c | /usr/bin/grep OK

/snap/bin/lxc file push yq_linux_amd64 runner/usr/bin/yq --mode +x

/snap/bin/lxc publish runner --alias runner --reuse -f
/snap/bin/lxc image export runner ./runner-image --vm
