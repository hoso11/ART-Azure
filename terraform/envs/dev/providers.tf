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

  # Task C2b — once shared_access_key_enabled = false on a storage account,
  # the azurerm provider's Read step still tries to fetch data-plane sub-
  # properties (queue_properties, share_properties, static_website,
  # blob_properties) and 403s with KeyBasedAuthenticationNotPermitted unless
  # this flag is set. With storage_use_azuread = true the provider uses the
  # Service Principal's Entra ID token for those reads instead. The SP must
  # therefore hold a Storage data-plane role on each storage account it
  # touches — "Storage Blob Data Owner" or "Storage Blob Data Contributor"
  # is sufficient. The SP already has effective Owner on the storage account
  # (via subscription-scope Owner during C2a), so reads succeed today; if
  # the SP is later downgraded to Contributor, grant it explicit
  # "Storage Blob Data Owner" on azurerm_storage_account.images to keep
  # plans/applies working.
  storage_use_azuread = true
}

provider "azapi" {
  # No explicit subscription_id / tenant_id — azapi uses ARM_* env vars,
  # the same ones azurerm picks up after `source .env.terraform`.
}
