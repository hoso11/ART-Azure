terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    # azapi is used for resources that don't yet have a native azurerm
    # type, specifically Microsoft.Web/sites/sitecontainers (Phase 2
    # sidecar containers). Same auth as azurerm — both providers honor
    # the ARM_CLIENT_ID / ARM_CLIENT_SECRET / ARM_TENANT_ID /
    # ARM_SUBSCRIPTION_ID env vars from .env.terraform, so no extra
    # credentials are required.
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
    # random provider — generates the Postgres admin password at apply time.
    # Stored in Terraform state (sensitive). No Azure API calls.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local state on purpose for Phase 1/2.
  # Remote backend (Azure Storage Account + blob lease lock) comes later.
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

provider "azapi" {
  # No explicit subscription_id / tenant_id — azapi uses ARM_* env vars,
  # the same ones azurerm picks up after `source .env.terraform`.
}
