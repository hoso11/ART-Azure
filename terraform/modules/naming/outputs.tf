# Naming convention (loosely follows Azure CAF):
#   <type-prefix>-<project>-[<workload>-]<environment>[-<suffix>]
#
# Region is omitted — the project is single-region (West Europe) per the
# hard rule in CLAUDE.md. If multi-region is ever introduced, add a
# region_short input (e.g. 'we') and splice it in here.
#
# Suffix is appended only to resources that need GLOBAL uniqueness
# (Web App hostnames, Storage Account names, Key Vault names, etc.).
# It is NOT applied to resources that are unique within their RG / sub
# (Resource Group, App Service Plan, Postgres database, ...).
#
# Phase 1 outputs only the three resources currently provisioned. Phase 2+
# adds backend, worker, postgres, redis, storage, key_vault, etc. as new
# outputs here — keeps every name change in one file.

output "resource_group" {
  description = "Resource group. Unique per environment within the subscription."
  value       = "rg-${var.project}-${var.environment}"
}

output "app_service_plan" {
  description = "Frontend App Service Plan."
  value       = "asp-${var.project}-${var.environment}"
}

output "app_service_plan_backend" {
  description = "Backend App Service Plan (Phase 2 — separate F1 plan per user request)."
  value       = "asp-${var.project}-backend-${var.environment}"
}

output "web_app_frontend" {
  description = "Frontend Linux Web App. Globally unique → uses suffix."
  value       = "app-${var.project}-frontend-${var.environment}-${var.suffix}"
}

output "web_app_backend" {
  description = "Backend Linux Web App. Globally unique → uses suffix."
  value       = "app-${var.project}-backend-${var.environment}-${var.suffix}"
}

output "postgres_server" {
  description = "PostgreSQL Flexible Server name. Globally unique under *.postgres.database.azure.com → uses suffix. Lowercase letters/digits/hyphens only."
  value       = "psql-${var.project}-${var.environment}-${var.suffix}"
}

output "storage_account_images" {
  description = "Storage Account name for product images. Globally unique under *.blob.core.windows.net → uses suffix. Storage Account names must be 3–24 lowercase alphanumeric characters, NO hyphens, so the convention here drops the dashes used elsewhere."
  value       = "st${var.project}${var.environment}imgs${var.suffix}"
  # e.g. project=art, environment=dev, suffix=art4242 → startdevimgsart4242 (19 chars)
}

output "tags" {
  description = "Standard tag set applied to every resource. Extend with cost-center / owner when those policies arrive."
  value = {
    Application = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
