# How to set base image

This charm supports deploying the runners on different base images.

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the
[charm configuration labels](https://charmhub.io/github-runner/configure#base-image), the runner
can be deployed with a different Ubuntu base image. The supported base images are limited to jammy
and noble to ensure guaranteed capabilities.

```shell
juju config <APP_NAME> base-image=<BASE_IMAGE_TAG_OR_NAME>
```

An example of a BASE_IMAGE_TAG_OR_NAME value would be "jammy", "22.04", "noble", "24.04".
