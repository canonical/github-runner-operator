# External Access

The GitHub Runner Charm itself requires access to the

- GitHub API (e.g. to register and remove runners).
- GitHub website (e.g. to download the runner binary or other applications like yq)
- Ubuntu package repositories (e.g. to install packages)
- Snap store (e.g. to install LXD or aproxy)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/) (for the image used by a runner)
- npm registry to download and install specific packages

In addition, access is required depending on the requirements of the workloads that the runners
will be running (as they will be running on the same machine as the charm).

More details on network configuration can be found in the
[charm architecture documentation](https://charmhub.io/github-runner/docs/charm-architecture).