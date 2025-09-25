<!-- vale Canonical.007-Headings-sentence-case = NO -->
# GitHub runner Terraform module
<!-- vale Canonical.007-Headings-sentence-case = YES -->

This folder contains a base [Terraform][Terraform] module for the GitHub runner charm.

The module uses the [Terraform Juju provider][Terraform Juju provider] to model the charm
deployment onto any Kubernetes environment managed by [Juju][Juju].

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment. Also models the charm configuration, 
  except for exposing the deployment options (Juju model name, channel or application name).
- **output.tf** - Integrates the module with other Terraform modules, primarily
  by defining potential integration endpoints (charm integrations), but also by exposing
  the Juju application name.
- **versions.tf** - Defines the Terraform provider version.

## Using github-runner base module in higher level modules

If you want to use `github-runner` base module as part of your Terraform module, import it
like shown below:

```text
data "juju_model" "my_model" {
  name = var.model
}

module "github_runner" {
  source = "git::https://github.com/canonical/github-runner-operator//terraform"

  model = juju_model.my_model.name
  # (Customize configuration variables here if needed)
}
```

Create integrations, for instance:

```text
resource "juju_integration" "ghib-gh" {
  model = juju_model.my_model.name
  application {
    name     = module.github_runner.app_name
    endpoint = module.github_runner.requires.github_runner_image_v0
  }
  application {
    name     = "github-runner-image-builder"
    endpoint = "image"
  }
}
```

The complete list of available integrations can be found [in the Integrations tab][github-runner-integrations].

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[github-runner-integrations]: https://charmhub.io/github-runner/integrations

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_juju"></a> [juju](#requirement\_juju) | >= 0.11.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_juju"></a> [juju](#provider\_juju) | >= 0.11.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [juju_application.github_runner](https://registry.terraform.io/providers/juju/juju/latest/docs/resources/application) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Name of the application in the Juju model. | `string` | `"github-runner"` | no |
| <a name="input_base"></a> [base](#input\_base) | The operating system on which to deploy | `string` | `"ubuntu@22.04"` | no |
| <a name="input_channel"></a> [channel](#input\_channel) | The channel to use when deploying a charm. | `string` | `"latest/stable"` | no |
| <a name="input_config"></a> [config](#input\_config) | Application config. Details about available options can be found at https://charmhub.io/github-runner/configurations | `map(string)` | `{}` | no |
| <a name="input_constraints"></a> [constraints](#input\_constraints) | Juju constraints to apply for this application. | `string` | `""` | no |
| <a name="input_model"></a> [model](#input\_model) | Reference to a `juju_model`. | `string` | `""` | no |
| <a name="input_revision"></a> [revision](#input\_revision) | Revision number of the charm | `number` | `null` | no |
| <a name="input_units"></a> [units](#input\_units) | Number of units to deploy | `number` | `1` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_app_name"></a> [app\_name](#output\_app\_name) | Name of the deployed application. |
| <a name="output_provides"></a> [provides](#output\_provides) | n/a |
| <a name="output_requires"></a> [requires](#output\_requires) | n/a |
<!-- END_TF_DOCS -->