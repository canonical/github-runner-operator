# How to spawn OpenStack runner

The charm can be configured to use OpenStack cloud for creating runners.
The charm must be deployed with the correct configuration and once the OpenStack integration is
enabled the charm cannot be changed to use other virtualization methods.

## Configuration

There are three configuration that the charm needs to be deployed with to enable OpenStack integration: `openstack-clouds-yaml`, `openstack-flavor`, and `openstack-network`.

### OpenStack clouds.yaml

The `openstack-clouds-yaml` configuration contains the authorization information needed for the charm to log in to the openstack cloud.
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

### OpenStack Flavor

The `openstack-flavor` configuration sets the flavor used to create the OpenStack virtual machine when spawning new runners.
The flavor is tied with the vCPU, memory, and storage.
The flavors documentation is [here](https://docs.openstack.org/nova/rocky/user/flavors.html).

### OpenStack Network

The  `openstack-network` configuration sets the network used to create the OpenStack virtual machine when spawning new runners.

Note that the network should be configured to allow traffic from the charm deployment (juju machine) to the OpenStack virtual machine, and traffic from the OpenStack virtual machine to GitHub.

The network documentation is [here](https://docs.openstack.org/neutron/latest/admin/intro-os-networking.html).
