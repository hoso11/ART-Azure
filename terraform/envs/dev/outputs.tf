# --- Frontend ----------------------------------------------------------------

output "frontend_url" {
  description = "Public HTTPS URL of the frontend Web App."
  value       = "https://${azurerm_linux_web_app.frontend.default_hostname}"
}

output "web_app_default_hostname" {
  description = "Frontend Web App hostname (kept for backward compatibility)."
  value       = azurerm_linux_web_app.frontend.default_hostname
}

output "web_app_url" {
  description = "Alias of frontend_url for backward compatibility."
  value       = "https://${azurerm_linux_web_app.frontend.default_hostname}"
}

# --- Backend (Phase 2) -------------------------------------------------------

output "backend_url" {
  description = "Public HTTPS URL of the backend Web App. Phase 3: Postgres is now provisioned in the same apply, so alembic should complete cleanly and /health returns 200 once the cold start finishes (2–5 min)."
  value       = "https://${azurerm_linux_web_app.backend.default_hostname}"
}

output "backend_default_hostname" {
  description = "Backend Web App default hostname."
  value       = azurerm_linux_web_app.backend.default_hostname
}

output "backend_image" {
  description = "Backend container image:tag deployed to the main + worker sidecars."
  value       = "${var.backend_image}:${var.backend_image_tag}"
}

output "backend_enabled_state" {
  description = "Whether the backend Web App is configured to run. 'stopped' = no containers running, zero CPU. 'running' = containers will be pulled and started by Azure (Phase 3 default — Postgres is now provisioned)."
  value       = var.backend_enabled ? "running" : "stopped"
}

# --- Phase 3: PostgreSQL Flexible Server ------------------------------------

output "postgres_server_name" {
  description = "Name of the Azure PostgreSQL Flexible Server (e.g. psql-art-dev-<suffix>)."
  value       = azurerm_postgresql_flexible_server.this.name
}

output "postgres_fqdn" {
  description = "Fully-qualified DNS name of the Postgres server (e.g. psql-art-dev-<suffix>.postgres.database.azure.com). Use this from psql / pgAdmin."
  value       = azurerm_postgresql_flexible_server.this.fqdn
}

output "postgres_database" {
  description = "Application database name created on the Flexible Server."
  value       = azurerm_postgresql_flexible_server_database.app.name
}

output "postgres_admin_user" {
  description = "Postgres administrator login. Passed to the backend via DATABASE_URL / DATABASE_URL_SYNC App Settings."
  value       = var.postgres_admin_user
}

output "postgres_admin_password" {
  description = "Auto-generated Postgres admin password (24 chars, URL-safe specials only). Read with `terraform output -raw postgres_admin_password`. Treat as a secret — stored in terraform.tfstate, never in tfvars."
  value       = random_password.postgres_admin.result
  sensitive   = true
}

# --- Sidecar status ---------------------------------------------------------

output "worker_sidecar_enabled" {
  description = "True if the Celery worker sidecar is provisioned."
  value       = var.worker_sidecar_enabled
}

output "redis_sidecar_enabled" {
  description = "True if the Redis sidecar is provisioned."
  value       = var.redis_sidecar_enabled
}

output "minio_sidecar_enabled" {
  description = "True if the MinIO sidecar is provisioned. Default false now — Azure deploys use Azure Blob Storage instead. Set true only if you switch backend_storage_backend back to 'minio'."
  value       = var.minio_sidecar_enabled
}

# --- Phase 4: Azure Blob Storage --------------------------------------------

output "storage_account_name" {
  description = "Name of the Azure Storage Account used for product images."
  value       = azurerm_storage_account.images.name
}

output "storage_account_primary_blob_endpoint" {
  description = "Primary blob endpoint URL (e.g. https://startdevimgsart4242.blob.core.windows.net/). The container is private; bytes flow through the backend proxy /api/v1/products/images/file/{key}."
  value       = azurerm_storage_account.images.primary_blob_endpoint
}

output "storage_container_name" {
  description = "Blob container name for product images."
  value       = azurerm_storage_container.images.name
}

output "storage_account_connection_string" {
  description = "Storage Account connection string. Read with `terraform output -raw storage_account_connection_string` if you need to debug. Wired into the backend Web App App Settings as AZURE_STORAGE_CONNECTION_STRING."
  value       = azurerm_storage_account.images.primary_connection_string
  sensitive   = true
}

# --- Resource names ---------------------------------------------------------

output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "frontend_app_service_plan_name" {
  value = azurerm_service_plan.frontend.name
}

output "backend_app_service_plan_name" {
  value = azurerm_service_plan.backend.name
}

output "frontend_web_app_name" {
  value = azurerm_linux_web_app.frontend.name
}

output "backend_web_app_name" {
  value = azurerm_linux_web_app.backend.name
}

output "deployed_image" {
  description = "Frontend container image:tag (kept for backward compatibility)."
  value       = "${var.frontend_image}:${var.frontend_image_tag}"
}

# --- Naming preview (sanity check) ------------------------------------------

output "names_preview" {
  description = "Names that the naming module computed for this environment."
  value = {
    resource_group           = module.naming.resource_group
    app_service_plan         = module.naming.app_service_plan
    app_service_plan_backend = module.naming.app_service_plan_backend
    web_app_frontend         = module.naming.web_app_frontend
    web_app_backend          = module.naming.web_app_backend
    postgres_server          = module.naming.postgres_server
  }
}
