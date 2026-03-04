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
- **output.tf** - Responsible for integrating the module with other Terraform modules, primarily by defining potential integration endpoints (charm integrations).
- **versions.tf** - Defines the Terraform provider.

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[Github runner charm]: https://charmhub.io/github-runner
[Github runner image builder charm]: https://charmhub.io/github-runner-image-builder

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0.0 |
| <a name="requirement_juju"></a> [juju](#requirement\_juju) | >= 1.0.0, < 2.0.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_juju"></a> [juju](#provider\_juju) | >= 1.0.0, < 2.0.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_github_runner"></a> [github\_runner](#module\_github\_runner) | ../charm | n/a |
| <a name="module_github_runner_image_builder"></a> [github\_runner\_image\_builder](#module\_github\_runner\_image\_builder) | git::https://github.com/canonical/github-runner-image-builder-operator//terraform/charm | rev143 |

## Resources

| Name | Type |
|------|------|
| [juju_integration.image_builder](https://registry.terraform.io/providers/juju/juju/latest/docs/resources/integration) | resource |
| [juju_model.github_runner](https://registry.terraform.io/providers/juju/juju/latest/docs/data-sources/model) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_github_runner_image_builder"></a> [github\_runner\_image\_builder](#input\_github\_runner\_image\_builder) | n/a | <pre>object({<br/>    app_name    = optional(string, "github-runner-image-builder")<br/>    channel     = optional(string, "latest/stable")<br/>    config      = optional(map(string), {})<br/>    constraints = optional(string, "arch=amd64 cores=2 mem=8192M root-disk=20000M")<br/>    revision    = optional(number)<br/>    base        = optional(string, "ubuntu@22.04")<br/>    units       = optional(number, 1)<br/>  })</pre> | n/a | yes |
| <a name="input_github_runners"></a> [github\_runners](#input\_github\_runners) | n/a | <pre>list(object({<br/>    app_name    = optional(string, "github-runner")<br/>    channel     = optional(string, "latest/stable")<br/>    config      = optional(map(string), {})<br/>    constraints = optional(string, "arch=amd64 cores=2 mem=8192M root-disk=20000M")<br/>    revision    = optional(number)<br/>    base        = optional(string, "ubuntu@22.04")<br/>    units       = optional(number, 1)<br/>    machines    = optional(set(string))<br/>  }))</pre> | n/a | yes |
| <a name="input_juju_model_owner"></a> [juju\_model\_owner](#input\_juju\_model\_owner) | n/a | `string` | `"admin"` | no |
| <a name="input_model"></a> [model](#input\_model) | Reference to the Juju model to deploy the github-runner and github-runner-image-builder operators. | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_all_app_names"></a> [all\_app\_names](#output\_all\_app\_names) | Names of the all the deployed apps, github-runner plus github-runner-image-builder. |
| <a name="output_all_runner_names"></a> [all\_runner\_names](#output\_all\_runner\_names) | Names of the all the deployed github-runner applications. |
| <a name="output_github_runner_image_builder_app_name"></a> [github\_runner\_image\_builder\_app\_name](#output\_github\_runner\_image\_builder\_app\_name) | Name of the the deployed github-runner-image-builder application. |
| <a name="output_reactive_runner_names"></a> [reactive\_runner\_names](#output\_reactive\_runner\_names) | Names of the all the deployed github-runner applications that are reactive. |
<!-- END_TF_DOCS -->
