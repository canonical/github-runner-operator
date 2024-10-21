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