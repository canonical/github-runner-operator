# How to setup reactive spawning

The charm provides an experimental feature to spawn runners reactively, depending on the jobs requested by GitHub.
This feature is disabled by default and can be enabled by integrating the charm with a MongoDB database.

## Requirements

You need to deploy a webhook router, which listens for incoming jobs, transforms them into
labels and stores those labels in a MongoDB database. You can use the [github-runnerwebhook-router charm](https://charmhub.io/github-runner-webhook-router) for this purpose.
The webhook router and the github runner charm must both be integrated with the same mongodb database.


## Steps

### Webhook router

The webhook router is a k8s charm, therefore you need to deploy it on a k8s cluster.

```shell

juju deploy github-runner-webhook-router --channel latest/edge --revision 30