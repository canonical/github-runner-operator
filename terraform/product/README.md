<!-- vale Canonical.007-Headings-sentence-case = NO -->
# Github runner Terraform modules
<!-- vale Canonical.007-Headings-sentence-case = YES -->

This project contains the [Terraform][Terraform] modules to deploy a list of [Github runner][Github runner charm] charms
integrated with one [Github runner image builder][Github runner image builder charm] charm.

The modules use the [Terraform Juju provider][Terraform Juju provider] to model
the bundle deployment onto any Kubernetes environment managed by [Juju][Juju].

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment including Juju model name, charm's channel and configuration.
- **outputs.tf** - Responsible for integrating the module with other Terraform modules, primarily by defining potential integration endpoints (charm integrations).
- **versions.tf** - Defines the Terraform provider.

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[Github runner charm]: https://charmhub.io/github-runner
[Github runner image builder charm]: https://charmhub.io/github-runner-image-builder
