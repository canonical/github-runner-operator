# How to set up reactive spawning

The charm provides an experimental feature to spawn runners reactively, depending on the jobs requested by GitHub.
This feature is only available for runners on OpenStack cloud and is
disabled by default and can be enabled by integrating the charm with a MongoDB charm.

## Requirements
For the purposes of this how-to-guide, we assume that you have a machine model (named "machine-model") 
that can be used to deploy runners on an OpenStack cloud and [MongoDB](https://charmhub.io/mongodb),
and a k8s model (named "k8s-model") for the [webhook router](https://charmhub.io/github-runner-webhook-router).

## Steps
We are going to showcase the steps required to set up a reactive spawning environment with three runner flavors (large, large-arm, small) and a MongoDB database as a message queue.

Note, that the specific revisions/channels in the steps are only marked here for reproducibility, you should adapt the revisions/channels to your needs.

### GitHub Runner Applications

For this how-to-guide, we decided to have deployed three GitHub Runner charm applications: `large`, `large-arm`, `small` . We need
to deploy those with these names, to comply with the routing table defined below.

```shell
juju switch machine-model
juju deploy github-runner large --channel latest/stable ....
juju deploy github-runner large-arm --channel latest/stable ....
juju deploy github-runner small --channel latest/stable ....
```

Please refer to [How to spawn OpenStack runner](how-to/openstack-runner.md).
for more information on how to deploy the runners.

### MongoDB

You need to deploy a MongoDB application to use as a message queue. 
You can choose to use the machine charm or the k8s charm version, although we recommend using
the machine charm as the k8s version may not be reachable from outside the k8s cluster.

```shell
juju switch machine-model
juju deploy mongodb --channel 6/edge --revision 188 
juju expose mongodb
juju offer mongodb:database
juju grant <user-in-k8s-cloud> consume <offer-name>
```

Integrate with the runner charms

```shell
juju integrate large mongodb
juju integrate large-arm mongodb
juju integrate small mongodb
```

### Define a webhook in your organisation or repository where the self-hosted runners are registered

On your repository or organisation's page on Github, you need to go to the settings and create a Webhook
(e.g. https://github.com/canonical/github-runner-operator/settings/hooks). Please make sure to select

- the Webhook url to be the URL of the webhook router
- the content type `application/json`
- the secret you defined in the webhook router (if you have so, which is recommended for security reasons)
- the individual event "Workflow jobs" (and only this, as all other events will just be rejected by the webhook router)

### Webhook router

The webhook router is a k8s charm, therefore you need to deploy it on a k8s model.

First, define a routing table to decide which labels should be routed to which GitHub Runner charm application:

```shell
cat <<EOF > routing_table.yaml 
- large: [large, x64]
- large-arm: [large, arm64]
- small: [small]
EOF
```

We decide to route all jobs with any label combination in the set `large,x64` to the large application, `large,arm64` to large-arm,
and labels with `small` to small.
This means, depending on which labels your users are setting in the workflow file, a VM of a different runner application will be used to
execute the job.

Switch to the k8s model and deploy the webhook router charm:

```shell
juju switch k8s-model
juju deploy github-runner-webhook-router --channel latest/edge --revision 30 --config flavours=@routing_table.yaml --config default-flavour=small --config webhook-secret=<your-secret>
juju consume <offer-url>
juju integrate github-runner-webhook-router mongodb
```

>[!IMPORTANT]
> The webhook router needs to be deployed with the name `github-runner-webhook-router`, as the database name is currently hardcoded in the charm.


In this example we use "small" as the default runner application, to which all jobs with empty labels (or default labels such as `self-hosted`,`linux`) 
are routed to.


In order to be reachable from GitHub, you need to make the webhook publicly available, you will need an ingress or the traefik charm to expose the webhook router:

```shell
juju deploy nginx-ingress-integrator --channel latest/edge --revision 117 --config path-routes='/' --config service-hostname='githubu-runner-webhook-router.my.domain' --config trust=True
juju integrate nginx-ingress-integrator github-runner-webhook-router
```

### COS integration
You will probably also need some observability.
The GitHub Runner and MongoDB machine charm provide COS integration via the `cos-agent` endpoint, and the
Github Runner Webhook Router charm  provides the usual endpoints (`logging`, `metrics-endpoint`, `grafana-dashboard`). Please refer to
[How to integrate with COS](how-to/integrate-with-cos.md) and [Canonical Observability Stack (COS) documentation](https://charmhub.io/topics/canonical-observability-stack) 
for more information.