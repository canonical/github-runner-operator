# GitHub runner cryptographic overview
This document provides an overview of the cryptographic technologies used in the GitHub runner charm, including encryption/decryption, hashing, and digital signatures.

## Overall Description of Cryptographic Technology Use
The GitHub runner charm uses various cryptographic technologies to ensure secure communication and data integrity. The following sections describe each of the components.
### TLS
The GitHub runner communicates with GitHub to receive information about the workflows that need to be executed, retrieve information about how the repositories are set up and send back logs to the user about the result of executing workflows. This communication uses [urllib3](https://urllib3.readthedocs.io/en/stable/) under the hood using TLS 1.3.

In OpenStack mode, the runner creates virtual machines in OpenStack and uses these machines to run the workload. The GItHub runner charm interacts with the OpenStack API to create and manage virtual machines. These interactions are secured via TLS. The communication between these virtual machines and runner is done via SSH and secured by 256 byte keypairs.

[DockerHub charm](https://charmhub.io/docker-registry) is used as a cache between the official DockerHub and GitHub runners to avoid rate limiting. Communication between GitHub runners and DockerHub cache is secured via TLS 1.3 and certified by [Let’s Encrypt](https://letsencrypt.org/).

Images that run in the OpenStack vm are built using the [Image Builder Charm](https://github.com/canonical/github-runner-image-builder-operator). This charm needs to download the runner binary, cloud image to base the image on and yq. All these images are downloaded with TLS.

The GitHub runner charm supports being deployed behind a HTTP proxy. [Aproxy](https://github.com/canonical/aproxy) is installed and enabled when a HTTP proxy is detected so that jobs executing in the runner VMs don’t have to configure the proxy themselves. Aproxy is a transparent proxy service for HTTP and HTTPS/TLS connections. Aproxy works by pre-reading the Host header in HTTP requests and SNI in TLS hellos; it forwards HTTP proxy requests with the hostname and, therefore, complies with HTTP proxies requiring destination hostname for auditing or access control. Aproxy is quite secure, as it doesn't and can't decrypt the TLS connections. It works by reading the plaintext SNI information in the client hello during the TLS handshake, so the authentication and encryption of TLS are never compromised. Aproxy supports TLS 1.0 and above except TLS 1.3 Encrypted Client Hello.
### Signature Verification
Cloud image is verified by SHA256 checksum. Runner binary is also downloaded by [GitHub Runner Charm](https://github.com/canonical/github-runner-operator) and verified by SHA256 in this charm.
### User SSH Access
Sometimes users need to access the vm instance that is running the workload, to establish this connection [Tmate](https://tmate.io/) is used. Tmate uses SSH protocol to secure shell connections between users and the GitHub runner. The connection is secured with rsa keypair and ed25519 fingerprints.
## Cryptographic Technology Used by the Product
The following cryptographic technologies are used internally by our product:
### TLS
- Communication with GitHub is done via TLS v1.3
- [The Repo Policy Compliance tool](https://github.com/canonical/repo-policy-compliance) communicates with the [GitHub API](https://docs.github.com/en/rest?apiVersion=2022-11-28) using TLS v1.3.
- Communication with the OpenStack API uses TLS v1.3.
### Signature Verification
Cloud images are verified by SHA256 checksum. Runner binary is also downloaded by [the GitHub Runner Charm](https://github.com/canonical/github-runner-operator) and verified by SHA256 in this charm.
### User SSH Access
Tmate secures SSH connections using [OpenSSL](https://www.openssl.org/).
### RSA
The communication between these virtual machines and runner is done via SSH and secured by RSA 256 byte keypairs.
## Cryptographic Technology Exposed to Users
The following sections describe the cryptographic technologies exposed to the user:
### Tmate
- [Tmate](https://tmate.io/) uses RSA (384 byte) and ED25519 (32 byte) fingerprints for connections from users to [Tmate](https://tmate.io/) and from the managers to [Tmate](https://tmate.io/). [OpenSSL](https://www.openssl.org/) is being used by [Tmate](https://tmate.io/) to secure the connection between user/manager to runner.
### Docker Hub Cache
[Docker Hub cache](https://github.com/canonical/docker-registry-charm) connection is secured via TLS 1.3 and certified by [Let’s Encrypt](https://letsencrypt.org/).
### Aproxy
[Aproxy](https://github.com/canonical/aproxy) supports TLS 1.0 and above except TLS 1.3 Encrypted Client Hello.
## Packages or Technology Providing Cryptographic Functionality
The following packages or technologies provide cryptographic functionality:
- [OpenSSL](https://www.openssl.org/) library is being used.
- For TLS and HTTPS connections urllib3 python library is used.
- Default clients in Ubuntu for SSH and TLS are being used.
- [Python hashlib](https://docs.python.org/3/library/hashlib.html) package is being used for sha256 checksum calculation/verification of runner binary and Cloud Init.
- OpenStack client is being used to generate keypairs.
- [Aproxy](https://github.com/canonical/aproxy) using the [golang.org/x/crypto](http://golang.org/x/crypto) package.
