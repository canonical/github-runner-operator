# How to spawn OpenStack runner

The charm can be configured to use OpenStack cloud for creating runners.
The charm must be deployed with the correct configuration, and once the OpenStack integration is
enabled, the charm cannot be changed to use other virtualization methods.

## Configuration

There are three configuration that the charm needs to be deployed with to enable OpenStack integration: `openstack-clouds-yaml`, `openstack-flavor`, and `openstack-network`.

## Integration

The image will take about 10-15 minutes to build and be fully integrated. Deploy the
`github-runner-image-builder` charm and wait for the image to be successfully provided via the
relation data.

```bash
juju deploy github-runner-image-builder
juju integrate github-runner-image-builder github-runner
juju status github-runner
```

The image will take about 10-15 minutes to build and be ready via the relation.

### OpenStack clouds.yaml

The `openstack-clouds-yaml` configuration contains the authorization information needed for the charm to log in to the OpenStack cloud.
The first cloud in the `clouds.yaml` is used by the charm.

Here is a sample of the `clouds.yaml`:

```yaml
clouds:
  cloud:
    auth:
      auth_url: https://keystone.cloud.com:5000/v3
      project_name: github-runner
      username: github-runner
      password: PASSWORD
      user_domain_name: Default
      project_domain_name: Default
    region_name: cloud
```

The `clouds.yaml` documentation is [here](https://docs.openstack.org/python-openstackclient/pike/configuration/index.html#clouds-yaml).

### OpenStack Flavour

The `openstack-flavor` configuration sets the flavour used to create the OpenStack virtual machine when spawning new runners.
The flavour is tied with the vCPU, memory, and storage.
The flavours documentation is [here](https://docs.openstack.org/nova/rocky/user/flavors.html).

### OpenStack Network

The `openstack-network` configuration sets the network used to create the OpenStack virtual machine when spawning new runners.

Note that the network should be configured to allow traffic from the charm deployment (Juju machine) to the OpenStack virtual machine, and traffic from the OpenStack virtual machine to GitHub.

The network documentation is [here](https://docs.openstack.org/neutron/latest/admin/intro-os-networking.html).

> NOTE: The name of the application must not be longer than 50 characters. A valid runner name is 64 characters or less in length and does not include '"', '/', ':',
'<', '>', '\', '|', '*' and '?'. 14 characters are reserved for Juju unit number and unique identifier.
