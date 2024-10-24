# How to setup reactive spawning

The charm provides an experimental feature to spawn runners reactively, depending on the jobs requested by GitHub.
This feature is disabled by default and can be enabled by integrating the charm with a MongoDB database.

## Requirements

You need to deploy a webhook router, which listens for incoming jobs, transforms them into
labels and stores those labels in a MongoDB database. You can use the [github-runnerwebhook-router charm](https://charmhub.io/github-runner-webhook-router) for this purpose.
The webhook router and the github runner charm must both be integrated with the same mongodb database.


## Steps
Note, the specific revisions/channels in the steps are only marked here to have the howto reproducible, you can adapt this to your needs.

### GitHub Runner flavors

For this howto, we decide to have deployed three runner flavors: large, large-arm, small . We need
to deploy those with these names, to comply with the routing table defined below.

```shell
juju switch machine-model
juju deploy github-runner large --channel latest/stable ....
juju deploy github-runner large-arm --channel latest/stable ....
juju deploy github-runner small --channel latest/stable ....
```

### MongoDB

You need to deploy a MongoDB application to use as Message Queue. You can choose to use the 
machine charm or k8s charm version, though we recommend using the machine charm as the k8s
version might not be reachable from outside the k8s cluster.

```shell

juju switch machine-model
juju deploy mongodb --channel 6/edge --revision 188 
juju expose mongodb
juju offer mongodb
```

Integrate with the github-runner charms

```shell
juju integrate large mongodb
juju integrate large-arm mongodb
juju integrate small mongodb
```

### Define a webhook in your organisation or repository where the self-hosted runners are registered.

On your repository or organisations page on Github, you need to go to the settings and create a Webhook.
The Webhook url needs to be the URL your router will be listening on, and the secret needs to be the secret you will use to authenticate the webhook.
You need to select the individual event "Workflow jobs".

### Webhook router

The webhook router is a k8s charm, therefore you need to deploy it on a k8s cluster.

First, define a routing table to decide which labels should be routed to which runner flavor

```shell
cat <<EOF > routing_table.yaml 
- large: [large, x64]
- large-arm: [large, arm64]
- small: [small]
```

We decide to route all jobs with labels large,x64 to the large flavor, large and arm64 to large-arm, and labels with small to small.

```shell
juju switch k8s-model
juju deploy github-runner-webhook-router --channel latest/edge --revision 30 --config flavors=@routing_table.yaml --config default-flavor=small
juju consume mongodb
juju integrate github-runner-webhook-router mongodb
```

In this example we use a default flavor called small, where all jobs with empty labels are assigned to.


We also need to make the webhook publicy available, so you probably need an ingress or traefik charm to expose the webhook router.

```shell
juju deploy nginx-ingress-integrator --channel latest/edge --revision 117 --config path-routes='/' --config service-hostname='githubu-runner-webhook-router.my.domain' --config trust=True
juju integrate nginx-ingress-integrator github-runner-webhook-router
```

