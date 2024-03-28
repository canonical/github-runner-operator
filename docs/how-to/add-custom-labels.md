# How to add custom labels

This charm supports adding custom labels to the runners.

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the
[charm configuration labels](https://charmhub.io/github-runner/configure#labels), additional 
custom labels can be attached to the self-hosted runners.

```shell
juju config <APP_NAME> labels=<COMMA_SEPARATED_LABELS>
```

An example of a COMMA_SEPARATED_LABELS value would be "large,gpu", "small,arm64".
Accepted values are alphanumeric values with underscores (_), whitespaces before and after the the
word will be automatically trimmed.