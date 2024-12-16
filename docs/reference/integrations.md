# Integrations

### debug-ssh

_Interface_: debug-ssh    
_Supported charms_: [tmate-ssh-server](https://charmhub.io/tmate-ssh-server)

Debug-ssh integration provides necessary information for runners to provide ssh reverse-proxy
applications to setup inside the runner. 

Example debug-ssh integrate command: 
```
juju integrate github-runner tmate-ssh-server
```


### mongodb

_Interface_: mongodb_client   
_Supported charms_: [mongodb](https://charmhub.io/mongodb), [mongodb-k8s](https://charmhub.io/mongodb-k8s)

The mongodb integration provides the necessary information for the runner manager to access
the mongodb database, which is required for the (experimental) reactive spawning feature.
Integrating the charm with mongodb lets the charm automatically go into reactive mode.

Example mongodb_client integrate command: 
```
juju integrate github-runner mongodb
```