# How to deploy on ARM64

The charm supports deployment on ARM64 machines. However, it should be noted that the ARM64
deployment currently only supports ARM64 bare-metal machines due to the limitations of
[nested virtualization on ARM64](https://developer.arm.com/documentation/102142/0100/Nested-virtualization).

The following uses AWS's [m7g.metal](https://aws.amazon.com/blogs/aws/now-available-bare-metal-arm-based-ec2-instances/)
instance to deploy the GitHub Runner on ARM64 architecture.

### Prerequisites
1. Juju with ARM64 bare metal instance availability.
    - On AWS: `juju bootstrap aws <desired-controller-name>`
2. GitHub [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
3. Repository to register the GitHub runners.

### Deployment steps

Run the following command:
```shell
juju deploy github-runner \
    --constraints="instance-type=a1.metal arch=arm64" \
    --config token=<PERSONAL-ACCESS-TOKEN> --config path=<OWNER/REPO>
```

The units may take several minutes to settle. Furthermore, due to charm restart (kernel update),
the Unit may become lost for a few minutes. This is an expected behavior and the unit should
automatically re-register itself onto the Juju controller after a successful reboot.

Goto the repository > Settings (tab) > Actions (left menu dropdown) > Runners and verify that the
runner has successfully registered and is online.