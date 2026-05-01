# --- Azure subscription / tenant ----------------------------------------------

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID. Required by the azurerm provider."
}

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID. Required by the azurerm provider."
}

# --- Region ------------------------------------------------------------------

variable "location" {
  type        = string
  description = "Azure region for ALL resources. F1 Free is available in West Europe. Single-region by design per CLAUDE.md."
  default     = "West Europe"
}

# --- Naming inputs (consumed by module.naming) -------------------------------

variable "project" {
  type        = string
  default     = "art"
  description = "Short project code."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment short name. Must be one of: dev, int, prod."
}

variable "suffix" {
  type        = string
  description = "Unique suffix for globally-unique resource names. 4–8 lowercase letters/digits."
}

# --- Frontend ----------------------------------------------------------------

variable "frontend_image" {
  type        = string
  default     = "hoso30/art-frontend"
  description = "Docker Hub image (no tag)."
}

variable "frontend_image_tag" {
  type        = string
  default     = "v24"
  description = "Frontend image tag. Pinned. v24 fixes browser-side fetches that had been broken since v22: the build was run from Git Bash on Windows, which let MSYS rewrite the `--build-arg NEXT_PUBLIC_API_URL=/api/v1` value to `C:/Program Files/Git/api/v1` before docker received it. That poisoned string was inlined by webpack into every clientFetch call, so all client-side requests (e.g. the production CreateBatchModal's product dropdown) threw `TypeError: Failed to fetch` in the browser. v24 was built with MSYS_NO_PATHCONV=1 set; the bundle now correctly uses `/api/v1` as the relative base URL. Build images from Git Bash with MSYS_NO_PATHCONV=1, or use a shell that doesn't path-mangle. v23 added defensive loading/error/refresh logic to the modal (still useful, kept). Do NOT use v21–v23 (poisoned), v13 (handoff/KNOWN_RISKS.md #2)."
  validation {
    condition     = !contains(["v13", "v21", "v22", "v23"], var.frontend_image_tag)
    error_message = "v13 and v21–v23 are forbidden — v13: poisoned (KNOWN_RISKS.md #2); v21: dev-mode Tailwind crash; v22–v23: MSYS path-mangled NEXT_PUBLIC_API_URL → all client-side fetches threw TypeError in the browser."
  }
}

variable "container_port" {
  type        = number
  default     = 3000
  description = "Frontend container listen port (Next.js standalone server.js → 3000)."
}

# --- Backend (Phase 2) -------------------------------------------------------

variable "backend_image" {
  type        = string
  default     = "hoso30/art-backend"
  description = "Backend (and worker) Docker Hub image. Worker reuses the same image with a different startup command."
}

variable "backend_image_tag" {
  type        = string
  default     = "v21"
  description = "Backend image tag. v21 makes the products image proxy backend-agnostic — it now streams via storage.download_file() so MinIO and Azure Blob both work; previously the proxy was MinIO-only and 404'd in Azure. v20 baseline: Azure Blob Storage adapter (azure-storage-blob SDK, app/storage/azure_adapter.py, products proxy + worker task switched to the StorageService abstraction). Required for STORAGE_BACKEND=azure. Do NOT use v13 — handoff/KNOWN_RISKS.md #2."
  validation {
    condition     = var.backend_image_tag != "v13"
    error_message = "v13 is forbidden — see handoff/KNOWN_RISKS.md #2 (poisoned image, failed migration 009)."
  }
}

variable "backend_port" {
  type        = number
  default     = 8000
  description = "Backend container listen port (uvicorn 0.0.0.0:8000)."
}

# --- Backend lifecycle -------------------------------------------------------
#
# Phase 2 ships the backend Web App in STOPPED state on purpose.
#
# The backend image's entrypoint.sh runs `alembic upgrade head` in an infinite
# retry loop. Without a real Postgres at DATABASE_URL_SYNC, that loop never
# exits and consumes ~33% of the F1 plan's CPU continuously. The F1 plan has
# only 60 CPU minutes / day total — the backend would burn the quota in ~3
# hours and then HTTP 403 every other app in the same plan until UTC midnight.
#
# Setting `enabled = false` on the backend Web App puts it in Azure's
# "Stopped" state: the Web App resource exists, App Settings and sidecars are
# fully configured in Terraform state, but NO container is pulled or run.
# Zero CPU consumed. F1 quota intact.
#
# When Postgres is provisioned in a later (separately-approved) task and
# DATABASE_URL_SYNC points at it, flip this default to `true` and rerun
# `terraform apply` — Azure will pull the images and start the containers.

variable "backend_enabled" {
  type        = bool
  default     = true
  description = "Whether the backend Web App should run. As of Phase 3, default is true — Postgres is provisioned in the same apply, so DATABASE_URL_SYNC points at a real DB and alembic completes cleanly. Set to false to stop the backend without destroying it (zero CPU, $0)."
}

# --- Worker sidecar ----------------------------------------------------------

variable "worker_sidecar_enabled" {
  type        = bool
  default     = true
  description = "Whether to provision the Celery worker sidecar. Set false to deploy without the worker (skips Celery, email tasks, daily stock check)."
}

variable "worker_startup_command" {
  type        = string
  default     = "celery -A app.worker.celery_app worker --beat --loglevel=info"
  description = "Worker startup command. Single command, no `bash -c \"...\"` wrapper — Azure's shell wrapper mangles embedded quotes (see AZURE_DEPLOYMENT.md). The --beat flag runs Celery Beat in the same process; fine for a single-instance dev deployment."
}

variable "worker_target_port" {
  type        = number
  default     = 9999
  description = "Arbitrary unused port for the worker sidecar. The worker doesn't listen, but Azure's sidecar API requires a target_port value."
}

# --- Redis sidecar -----------------------------------------------------------

variable "redis_sidecar_enabled" {
  type        = bool
  default     = true
  description = "Whether to provision the Redis sidecar. Set false if you bring your own broker."
}

variable "redis_image" {
  type        = string
  default     = "redis"
  description = "Redis Docker Hub image (no tag)."
}

variable "redis_image_tag" {
  type    = string
  default = "7-alpine"
}

variable "redis_port" {
  type        = number
  default     = 6379
  description = "Redis listen port — internal only, never exposed publicly because only the Web App's main container port (8000) is public."
}

# --- MinIO sidecar -----------------------------------------------------------
#
# Required when backend_storage_backend = "minio" (the default). The backend's
# MinIOStorageService eagerly calls bucket_exists() in __init__, so without a
# reachable MinIO server every endpoint that depends on get_storage_service()
# (including /products/public) returns 500. The sidecar runs on the existing
# backend F1 plan — no new SKU, no new plan, $0.

variable "minio_sidecar_enabled" {
  type        = bool
  default     = false
  description = "Whether to provision the MinIO sidecar. DEFAULT false now that Azure Blob is the supported storage backend in Azure (azure_adapter.py is shipped in backend image v20). Set true only if you switch backend_storage_backend back to 'minio' for some local-style sidecar test — pairs with the port-collision workaround on 9100/9101."
}

variable "minio_image" {
  type        = string
  default     = "minio/minio"
  description = "MinIO Docker Hub image (no tag)."
}

variable "minio_image_tag" {
  type        = string
  default     = "latest"
  description = "MinIO image tag. 'latest' matches docker-compose.azure.yml. Pin to a RELEASE.* tag if you need reproducibility."
}

variable "minio_port" {
  type        = number
  default     = 9100
  description = "MinIO data port — internal only, reached by the backend at 127.0.0.1:<port>. NOT 9000: Azure App Service Linux runs PHP-FPM on 9000 inside every Web App's network namespace as part of the platform base image, so any sidecar binding 9000 collides ('unable to bind listening socket: Address already in use'), the platform SIGTERMs the multi-container app, and everything restarts in a loop. 9100 is free."
}

variable "minio_console_port" {
  type        = number
  default     = 9101
  description = "MinIO console port — internal only. Bound via --console-address. Moved off 9001 in lockstep with minio_port to keep both ports above the App Service platform's reserved 9000 zone."
}

variable "minio_access_key" {
  type        = string
  default     = "minioadmin"
  description = "MinIO root credentials (legacy alias of MINIO_ROOT_USER). Default 'minioadmin' matches the MinIO Docker image's default — keep them aligned. Replace before any real use."
  sensitive   = true
}

variable "minio_secret_key" {
  type        = string
  default     = "minioadmin"
  description = "MinIO root credentials (legacy alias of MINIO_ROOT_PASSWORD). Default 'minioadmin' matches the MinIO Docker image's default. Replace before any real use."
  sensitive   = true
}

variable "minio_bucket" {
  type        = string
  default     = "art-images"
  description = "Bucket name auto-created by MinIOStorageService._ensure_bucket on first request. Public-read policy is applied automatically."
}

# --- Backend app settings (placeholders) -------------------------------------

variable "backend_secret_key" {
  type        = string
  default     = "placeholder-dev-secret-change-me"
  description = "JWT signing key. Placeholder for Phase 2 — replace via App Settings or Key Vault before any real use."
  sensitive   = true
}

# Phase 3 NOTE: backend_database_url / backend_database_url_sync used to be
# placeholder variables. They are now COMPUTED in main.tf from the real
# Postgres resource (azurerm_postgresql_flexible_server.this) — no variable
# is needed. If you have these in terraform.tfvars from an older copy of
# tfvars.example, delete them to avoid an "undeclared variable" warning.

variable "backend_storage_backend" {
  type        = string
  default     = "azure"
  description = "STORAGE_BACKEND. 'azure' (default in Azure deploys) uses the Azure Blob adapter against a managed Storage Account — no in-Web-App MinIO sidecar, no port collision, free 5 GB / 20k reads / 10k writes. 'minio' is local-dev-only (docker-compose) and is also still valid here if you want to fall back to a sidecar."
  validation {
    condition     = contains(["minio", "azure"], var.backend_storage_backend)
    error_message = "backend_storage_backend must be 'minio' or 'azure'."
  }
}

variable "azure_storage_container" {
  type        = string
  default     = "art-images"
  description = "Blob container name for product images. Auto-created by AzureBlobStorageService._ensure_container on first request (idempotent — swallows ResourceExistsError)."
}

# --- Phase 3: PostgreSQL Flexible Server -------------------------------------
#
# B1MS Burstable, 32 GB storage, 32 GB backup, 7-day retention. This exact
# combo is the 12-month-free configuration per CLAUDE.md §3 allowlist.
# Constraints baked into validation rules below — Terraform will refuse to
# plan a paid configuration.

variable "postgres_version" {
  type        = string
  default     = "16"
  description = "PostgreSQL major version. Matches the local postgres:16-alpine in docker-compose.yml. Free tier supports 11–17."
}

variable "postgres_sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "PG SKU. ONLY B_Standard_B1ms is free-tier-eligible — Terraform will reject anything else."
  validation {
    condition     = var.postgres_sku_name == "B_Standard_B1ms"
    error_message = "Only B_Standard_B1ms is allowed (12-month free tier per CLAUDE.md §3 Azure Free Resources Allowlist)."
  }
}

variable "postgres_storage_mb" {
  type        = number
  default     = 32768 # 32 GB
  description = "Storage in MB. 32768 = 32 GB = the free-tier limit. Going above incurs ~$0.115/GB/month."
  validation {
    condition     = var.postgres_storage_mb <= 32768
    error_message = "postgres_storage_mb must be <= 32768 (32 GB) to stay within the free-tier allowance."
  }
}

variable "postgres_backup_retention_days" {
  type        = number
  default     = 7
  description = "Backup retention. 7 days is the minimum and matches free-tier inclusion of up to 32 GB backup. Going higher is allowed (Azure permits 7–35) but uses more backup storage."
  validation {
    condition     = var.postgres_backup_retention_days >= 7 && var.postgres_backup_retention_days <= 35
    error_message = "Azure PG Flexible Server allows 7–35 day backup retention."
  }
}

variable "postgres_admin_user" {
  type        = string
  default     = "art_admin"
  description = "PG admin login. Azure forbids 'admin', 'administrator', 'azure_*', 'pg_*', 'public', 'root'."
  validation {
    condition     = !contains(["admin", "administrator", "public", "root"], lower(var.postgres_admin_user)) && !startswith(lower(var.postgres_admin_user), "azure_") && !startswith(lower(var.postgres_admin_user), "pg_")
    error_message = "postgres_admin_user cannot be 'admin'/'administrator'/'public'/'root' or start with 'azure_'/'pg_' (Azure restriction)."
  }
}

variable "postgres_database_name" {
  type        = string
  default     = "art_manufacturing"
  description = "Application database name on the Flexible Server."
}

# Region exception for PostgreSQL only.
#
# All other resources in this environment live in `var.location` (West Europe).
# Azure blocks PostgreSQL Flexible Server provisioning in West Europe for
# certain subscription types (trial / Visual Studio / MOSP / Students / etc.)
# with the error LocationIsOfferRestricted. The resource group stays in West
# Europe; only the Postgres server itself uses this region.
#
# When the West Europe block is lifted (quota request approved or subscription
# upgraded), change this default back to "West Europe" and run terraform apply
# — the server will be recreated (data loss; pg_dump first if data exists).
#
# Cross-region egress between West Europe (Web App) and North Europe (PG) stays
# inside the free 100 GB outbound allowance for dev workloads.
variable "postgres_location" {
  type        = string
  default     = "North Europe"
  description = "Azure region for the PostgreSQL Flexible Server only. All other resources use var.location. Default North Europe is the closest free-tier region to West Europe (~10 ms RTT). Free-tier B1MS offer is available in this region."
}
