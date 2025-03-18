locals {
  juju_model_name               = "stg-ps6-github-runner"
  juju_image_builder_model_name = local.juju_model_name

  path = "javierdelapuente/github-runner-operator"

  # just one to test.
  openstack_flavor              = "m1.builder"
  openstack_network             = "external-network"
  openstack_auth_url            = "http://192.168.20.13/openstack-keystone/v3"
  openstack_project_name        = "demo"
  openstack_username            = "demo"
  openstack_password            = "demo"
  openstack_user_domain_name    = "users"
  openstack_project_domain_name = "users"
  openstack_clouds_yaml         = <<EOT
    clouds:
      prodstack5:
        auth:
          auth_url: ${local.openstack_auth_url}
          project_name: ${local.openstack_project_name}
          username: ${local.openstack_username}
          password: ${local.openstack_password}
          user_domain_name: ${local.openstack_user_domain_name}
          project_domain_name: ${local.openstack_project_domain_name}
        region_name: RegionOne
  EOT

}

module "github_runner" {
  source                            = "../product"
  model                             = local.juju_model_name
  github_runner_image_builder_model = local.juju_image_builder_model_name
  github_runner                     = {}
  github_runner_image_builder = {
    config = {
      architecture                  = "amd64"
      base-image                    = "jammy"
      openstack-auth-url            = local.openstack_auth_url
      openstack-password            = local.openstack_password
      openstack-project-domain-name = local.openstack_project_domain_name
      openstack-project-name        = local.openstack_project_name
      openstack-user-domain-name    = local.openstack_user_domain_name
      openstack-user-name           = local.openstack_username
      build-flavor                  = local.openstack_flavor
      build-network                 = local.openstack_network
    }
  }

  providers = {
    juju                             = juju
    juju.github_runner_image_builder = juju.github_runner_image_builder
  }

  github_runners = [
    {
      app_name = "github-runner"
      config = {
        openstack-clouds-yaml = local.openstack_clouds_yaml
        base-virtual-machines = 1
        path                  = local.path
        token                 = var.github_token
        openstack-flavor      = local.openstack_flavor
      }
    },
    {
      app_name = "github-runner-reactive"
      config = {
        openstack-clouds-yaml      = local.openstack_clouds_yaml
        max-total-virtual-machines = 1
        path                       = local.path
        token                      = var.github_token
        openstack-flavor           = local.openstack_flavor
      }
    }
  ]

}
