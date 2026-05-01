# Phase 1 + Phase 2 dev deployment to Azure.
#
# Phase 1: frontend Web App on its own F1 plan (asp-art-dev).
# Phase 2: SECOND F1 plan (asp-art-backend-dev) hosting a backend Web App
#          with three sidecar containers — backend (main), worker, redis.
#
# Both plans are F1 Free. No Postgres, Storage, Key Vault, ACR, monitoring,
# or networking resources in this scope — those are deferred to later phases
# pending explicit approval per CLAUDE.md cost guardrails.
#
# Known limitations of Phase 2 — these are not Terraform bugs:
#   1. Backend container will spin in alembic-retry until DATABASE_URL
#      points at a real Postgres. See backend/entrypoint.sh (infinite loop).
#   2. Frontend image hoso30/art-frontend:v19 has INTERNAL_API_URL baked at
#      build time. Setting it as an App Setting has no effect until a new
#      frontend image is built with the new backend URL as a build-arg.

# --- Naming ------------------------------------------------------------------

module "naming" {
  source = "../../modules/naming"

  project     = var.project
  environment = var.environment
  suffix      = var.suffix
}

# --- State refactors ---------------------------------------------------------
# Phase 1 had a single azurerm_service_plan.this. Phase 2 splits it into
# .frontend and .backend. The `moved` block tells Terraform that the
# resource at .this is now at .frontend — pure state rename, no destroy /
# recreate, no live downtime on the existing frontend Web App.
moved {
  from = azurerm_service_plan.this
  to   = azurerm_service_plan.frontend
}

# --- Resource group ----------------------------------------------------------

resource "azurerm_resource_group" "this" {
  name     = module.naming.resource_group
  location = var.location
  tags     = module.naming.tags
}

# --- Phase 1: frontend plan + Web App ---------------------------------------

# F1 Free — Linux. Constraints (platform-enforced):
#   1 instance, no scale-out, 60 CPU min/day, 1 GB RAM, no always_on,
#   no slots, no VNet, no custom-domain SSL, default *.azurewebsites.net
#   hostname has a Microsoft-managed cert.
resource "azurerm_service_plan" "frontend" {
  name                = module.naming.app_service_plan
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  os_type             = "Linux"
  sku_name            = "F1"
  tags                = module.naming.tags
}

resource "azurerm_linux_web_app" "frontend" {
  name                = module.naming.web_app_frontend
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_service_plan.frontend.location
  service_plan_id     = azurerm_service_plan.frontend.id

  https_only = true

  site_config {
    always_on           = false
    ftps_state          = "Disabled"
    minimum_tls_version = "1.2"

    application_stack {
      docker_image_name   = "${var.frontend_image}:${var.frontend_image_tag}"
      docker_registry_url = "https://index.docker.io"
    }
  }

  app_settings = {
    WEBSITES_PORT                       = tostring(var.container_port)
    WEBSITES_ENABLE_APP_SERVICE_STORAGE = "false"
    NODE_ENV                            = "production"

    # Phase 2: point the frontend at the backend Web App.
    #
    # IMPORTANT — these two values are baked into the frontend image at
    # build time (ARG → ENV → next build freezes them into the bundle and
    # routes-manifest.json). Setting them as Azure App Settings is a no-op
    # for the JS bundle and the rewrite destination; they take effect ONLY
    # via the matching --build-arg at image build time. We declare them
    # here anyway so:
    #   (a) the intended values are visible in the portal,
    #   (b) any future SSR-side runtime read works without a Terraform change,
    #   (c) the image (v20) was built with the SAME values as below — keep
    #       them in lockstep when bumping frontend_image_tag.
    #
    # OPTION A architecture (browser stays same-origin via Next.js rewrites):
    #   - INTERNAL_API_URL: absolute backend URL. The /api/* rewrite in
    #     next.config.js proxies browser-originated /api/v1/... requests
    #     from the frontend Web App to the backend Web App.
    #   - NEXT_PUBLIC_API_URL: relative '/api/v1'. clientFetch builds
    #     same-origin URLs, so SameSite=Lax cookies set by the backend are
    #     forwarded by Next.js to the frontend's origin and ride every
    #     subsequent fetch unchanged.
    INTERNAL_API_URL    = "https://${module.naming.web_app_backend}.azurewebsites.net"
    NEXT_PUBLIC_API_URL = "/api/v1"
  }

  tags = module.naming.tags
}

# --- Phase 2: backend plan + Web App + sidecars -----------------------------

# Second F1 Linux plan — separate from frontend per user's Phase 2 design.
# Same F1 limits apply independently to this plan.
resource "azurerm_service_plan" "backend" {
  name                = module.naming.app_service_plan_backend
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  os_type             = "Linux"
  sku_name            = "F1"
  tags                = module.naming.tags
}

# Backend Web App. Multi-container — `application_stack` is intentionally
# OMITTED. All containers (main + sidecars) are configured below via the
# azurerm_app_service_site_container resource, mirroring the
# `az webapp sitecontainers create` API. App settings declared here are
# injected into EVERY container in the app (main + worker + redis).
#
# IMPORTANT — `enabled` defaults to false (see var.backend_enabled).
# Phase 2 ships the Web App in Azure's "Stopped" state on purpose, because
# backend/entrypoint.sh runs `alembic upgrade head` in an infinite retry
# loop. With placeholder DATABASE_URL_SYNC, that loop would burn the F1
# plan's 60 CPU min/day quota in ~3 hours. Stopped state = zero CPU, all
# config staged. Flip var.backend_enabled to true once Postgres is wired.
resource "azurerm_linux_web_app" "backend" {
  name                = module.naming.web_app_backend
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_service_plan.backend.location
  service_plan_id     = azurerm_service_plan.backend.id

  enabled    = var.backend_enabled
  https_only = true

  site_config {
    always_on           = false
    ftps_state          = "Disabled"
    minimum_tls_version = "1.2"
    # No application_stack — see comment above.
  }

  app_settings = {
    # Azure platform
    WEBSITES_PORT                       = tostring(var.backend_port)
    WEBSITES_ENABLE_APP_SERVICE_STORAGE = "false"

    # General
    APP_ENV    = "production"
    DEBUG      = "false"
    LOG_FORMAT = "json"

    # Auth
    SECRET_KEY                      = var.backend_secret_key
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = "15"
    JWT_REFRESH_TOKEN_EXPIRE_DAYS   = "7"

    # CORS — must match the public frontend hostname exactly (scheme + host,
    # no trailing slash). Login cookies depend on this.
    ALLOWED_ORIGINS = "https://${module.naming.web_app_frontend}.azurewebsites.net"

    # Database — Phase 3 wires the real Azure PostgreSQL Flexible Server.
    # asyncpg uses ?ssl=require; psycopg2 (alembic + worker) uses ?sslmode=require.
    # The two DSNs are NOT interchangeable: wrong SSL keyword fails server-side.
    # Password is interpolated raw — random_password.override_special restricts
    # special chars to URL-safe ones, so no urlencode wrapper is needed.
    DATABASE_URL      = "postgresql+asyncpg://${var.postgres_admin_user}:${random_password.postgres_admin.result}@${azurerm_postgresql_flexible_server.this.fqdn}:5432/${var.postgres_database_name}?ssl=require"
    DATABASE_URL_SYNC = "postgresql://${var.postgres_admin_user}:${random_password.postgres_admin.result}@${azurerm_postgresql_flexible_server.this.fqdn}:5432/${var.postgres_database_name}?sslmode=require"

    # Redis / Celery — sidecars share the parent Web App's network namespace,
    # so 127.0.0.1:6379 reaches the redis sidecar. Worker connects the same way.
    REDIS_URL             = "redis://127.0.0.1:${var.redis_port}/0"
    CELERY_BROKER_URL     = "redis://127.0.0.1:${var.redis_port}/0"
    CELERY_RESULT_BACKEND = "redis://127.0.0.1:${var.redis_port}/1"

    # Storage. 'azure' is the production path: backend image v20+ ships the
    # Azure Blob adapter (azure-storage-blob SDK) and reads
    # AZURE_STORAGE_CONNECTION_STRING / AZURE_STORAGE_CONTAINER below.
    # 'minio' would require provisioning the MinIO sidecar (currently
    # disabled by default — see var.minio_sidecar_enabled).
    STORAGE_BACKEND = var.backend_storage_backend

    # Azure Blob — connection string is sensitive. Stored in tfstate (gitignored)
    # and in App Settings (visible to portal-admins, same trust boundary as
    # the Postgres password). For a stricter setup, switch to System-Assigned
    # Managed Identity + Storage Blob Data Contributor role + DefaultAzureCredential
    # in code — deferred to a later phase.
    AZURE_STORAGE_CONNECTION_STRING = azurerm_storage_account.images.primary_connection_string
    AZURE_STORAGE_CONTAINER         = azurerm_storage_container.images.name
  }

  tags = module.naming.tags
}

# --- Backend sidecars -------------------------------------------------------
#
# Site containers (sidecars) are provisioned via the azapi provider against
# the Microsoft.Web/sites/sitecontainers ARM API. azurerm 4.70 does not yet
# expose a native resource for sitecontainers, so we use azapi to call the
# stable ARM API directly. azapi auth is the same ARM_* env vars azurerm
# uses, so no extra credentials.
#
# Exactly one site container has isMain = true; the rest are sidecars. All
# share the parent Web App's app_settings and network namespace (calls
# between containers go to 127.0.0.1).

resource "azapi_resource" "backend_main" {
  type      = "Microsoft.Web/sites/sitecontainers@2023-12-01"
  parent_id = azurerm_linux_web_app.backend.id
  name      = "backend"

  body = {
    properties = {
      image      = "${var.backend_image}:${var.backend_image_tag}"
      targetPort = tostring(var.backend_port)
      isMain     = true
      # No startUpCommand — use image default (entrypoint.sh runs alembic
      # + uvicorn). When backend_enabled = false, this never executes.
    }
  }
}

resource "azapi_resource" "backend_worker" {
  count = var.worker_sidecar_enabled ? 1 : 0

  type      = "Microsoft.Web/sites/sitecontainers@2023-12-01"
  parent_id = azurerm_linux_web_app.backend.id
  name      = "worker"

  body = {
    properties = {
      # Worker reuses the backend image with a different startup command.
      image = "${var.backend_image}:${var.backend_image_tag}"

      # Worker does NOT listen on any port. Azure still requires a
      # targetPort, so we use an arbitrary unused value. Nothing routes to it.
      targetPort = tostring(var.worker_target_port)
      isMain     = false

      # Single command, NO `bash -c "..."` wrapper — Azure's sidecar shell
      # wrapper eats embedded quotes (see AZURE_DEPLOYMENT.md "MinIO note").
      # The --beat flag runs Celery Beat in the same process; fine for a
      # single-instance dev deployment.
      startUpCommand = var.worker_startup_command
    }
  }
}

resource "azapi_resource" "backend_redis" {
  count = var.redis_sidecar_enabled ? 1 : 0

  type      = "Microsoft.Web/sites/sitecontainers@2023-12-01"
  parent_id = azurerm_linux_web_app.backend.id
  name      = "redis"

  body = {
    properties = {
      image      = "${var.redis_image}:${var.redis_image_tag}"
      targetPort = tostring(var.redis_port)
      isMain     = false
      # No startUpCommand — image's default `redis-server` binds
      # 0.0.0.0:6379 with no password, which is exactly what Celery expects.
    }
  }
}

# MinIO sidecar — S3-compatible object store the backend uses for product
# images. Required when backend_storage_backend = "minio".
#
# Persistence: MinIO writes to /data inside the container, which is ephemeral
# (lost on Web App restart). The bucket is auto-recreated on next start by
# MinIOStorageService._ensure_bucket. Acceptable for dev.
#
# Reachability: only the parent Web App's main port (8000) is public. MinIO
# data port 9000 and console 9001 are sidecar-internal — not reachable from
# the browser. Image URLs reach the browser via the backend proxy (see the
# big comment in app_settings about MINIO_EXTERNAL_ENDPOINT and
# /api/v1/products/images/file/{key}).
#
# Credentials: defaults to minioadmin/minioadmin to match the MinIO image's
# defaults and the backend's defaults — keep them aligned. Replace before
# real use via var.minio_access_key / var.minio_secret_key (the same value
# is the legacy alias for MINIO_ROOT_USER / MINIO_ROOT_PASSWORD on the
# server side).
resource "azapi_resource" "backend_minio" {
  count = var.minio_sidecar_enabled ? 1 : 0

  type      = "Microsoft.Web/sites/sitecontainers@2023-12-01"
  parent_id = azurerm_linux_web_app.backend.id
  name      = "minio"

  body = {
    properties = {
      image      = "${var.minio_image}:${var.minio_image_tag}"
      targetPort = tostring(var.minio_port)
      isMain     = false

      # Single command, NO bash -c wrapper — Azure's sidecar shell wrapper
      # mangles embedded quotes (see AZURE_DEPLOYMENT.md). The colon in
      # `:${port}` is a literal arg value (MinIO's --address / --console-address
      # accept an empty-host bind syntax). No quotes needed.
      #
      # `--address :${minio_port}` is REQUIRED. MinIO's default API port is
      # 9000 — the same port Azure App Service's platform PHP-FPM binds on
      # every Linux Web App. Without an explicit --address, MinIO binds 9000
      # and the platform fails to start FPM ("Address already in use"), Azure
      # SIGTERMs the whole multi-container app, and everything restarts in a
      # loop. Forcing MinIO to var.minio_port (default 9100) avoids the clash.
      startUpCommand = "minio server /data --address :${var.minio_port} --console-address :${var.minio_console_port}"
    }
  }
}

# --- Phase 3: PostgreSQL Flexible Server ------------------------------------
#
# B1MS Burstable, 12-month free tier per CLAUDE.md §3 allowlist:
#   - 750 compute hours/month (always-on B1MS uses ~720 — within limit)
#   - 32 GB storage, 32 GB backup (both at the free cap, no headroom)
#   - LRS backup, 7-day retention, no geo-redundant
#   - Single zone, no HA, no zone redundancy
#   - Public access + "AllowAzureServices" firewall rule
#
# CRITICAL: Free tier allows ONLY ONE eligible PostgreSQL Flexible Server
# per subscription. If another exists in this subscription, this server
# starts billing at full B1MS rate (~$15/month) immediately.
#
# Free tier window is 12 months from subscription creation, NOT server
# creation. When the window closes, the server flips to paid automatically.

resource "random_password" "postgres_admin" {
  length  = 24
  special = true
  upper   = true
  lower   = true
  numeric = true

  # Azure PG admin password requires at least 3 of {uppercase, lowercase,
  # digits, non-alphanumeric}. Setting min_* explicitly guarantees this.
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
  min_special = 2

  # Restrict special chars to URL-unreserved per RFC 3986 — avoids any
  # URL-encoding ambiguity in DATABASE_URL / DATABASE_URL_SYNC.
  override_special = "_-"
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                = module.naming.postgres_server
  resource_group_name = azurerm_resource_group.this.name

  # Region EXCEPTION (see var.postgres_location): every other resource in this
  # env uses azurerm_resource_group.this.location (West Europe). Postgres uses
  # var.postgres_location because Azure blocked Flexible Server provisioning
  # in West Europe for this subscription (LocationIsOfferRestricted). The RG
  # itself stays in West Europe; only the server's compute and storage are
  # placed in postgres_location.
  location = var.postgres_location

  version    = var.postgres_version
  sku_name   = var.postgres_sku_name
  storage_mb = var.postgres_storage_mb

  # Auto-grow OFF on purpose — preserves the 32 GB free cap. If the DB
  # fills, writes fail (better than slipping into paid storage silently).
  # storage_tier defaults to P4 for 32 GB; left implicit.

  administrator_login    = var.postgres_admin_user
  administrator_password = random_password.postgres_admin.result

  backup_retention_days        = var.postgres_backup_retention_days
  geo_redundant_backup_enabled = false # not free at this tier

  public_network_access_enabled = true

  # zone = (omitted on purpose). Pinning to a specific AZ caused the first
  # apply to fail with "AvailabilityZoneNotAvailable: zone '1' isn't
  # available in 'westeurope' for subscription <id>" — not all subscriptions
  # get the same zone allocation in every region. Omitting `zone` lets Azure
  # place the server in any zone that is available for this subscription.
  # Zonal placement only matters for HA, which is not free at B1MS anyway.
  #
  # Once Azure has placed the server, it auto-assigns a zone (e.g. "1" in
  # North Europe). With no `zone` line in config, Terraform sees that as
  # drift ("1" → null) and tries to UPDATE the zone on every apply. Azure
  # rejects zone updates without an HA standby (paid). The
  # ignore_changes = [zone] below tells Terraform to accept whichever zone
  # Azure picked and stop fighting over it. Robust across regions/zones.

  # No high_availability block = HA disabled (HA is not free at B1MS).

  tags = module.naming.tags

  lifecycle {
    # Accept whatever zone Azure auto-assigns. Without this, every plan
    # after the first apply tries to UPDATE zone "1" → null, which Azure
    # rejects unless paid HA is enabled. See the comment block above.
    ignore_changes = [zone]

    # Defensive: if a future edit accidentally bumps SKU off B1MS, abort.
    precondition {
      condition     = var.postgres_sku_name == "B_Standard_B1ms"
      error_message = "Postgres SKU must remain B_Standard_B1ms (free-tier-only)."
    }

    # Critical Data Protection (handoff/SAFE_TASK_RULES.md "Critical Data
    # Protection"). The Postgres server holds application data — destroy or
    # replace would lose every order, product, customer, audit-log row.
    # Removing this requires an explicit user approval and a backup plan
    # (pg_dump first). The documented "North Europe → West Europe" recreate
    # is the only time this should ever be commented out, and only after
    # `pg_dump` has run successfully.
    prevent_destroy = true
  }
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.postgres_database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    # Critical Data Protection — the application database. Drop = lose all
    # rows. The Postgres server lifecycle block above also has prevent_destroy,
    # but locking the database independently means a config edit that
    # accidentally renames or moves this resource will also be refused.
    prevent_destroy = true
  }
}

# Magic firewall rule: 0.0.0.0 → 0.0.0.0 = "Allow access from any Azure
# service". Web App outbound traffic is recognized as Azure service traffic.
# Credentials are still required — this only opens the network path within
# the Azure backbone, never to the public internet.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# --- Phase 4: Azure Blob Storage for product images -------------------------
#
# Replaces the MinIO sidecar. Backend image v20+ uses
# AzureBlobStorageService (app/storage/azure_adapter.py) when
# STORAGE_BACKEND=azure (the default in main.tf above).
#
# Free tier (CLAUDE.md §3 Allowlist):
#   - Standard_LRS Hot block blob, 5 GB storage / 20k reads / 10k writes
#   - 12-month allowance (matches PG window — same subscription)
#
# Defenses against accidental cost:
#   - account_replication_type = "LRS" (GRS/ZRS bill from byte one)
#   - account_kind = "StorageV2" (premium tiers bill from byte one)
#   - allow_nested_items_to_be_public = false (private container by default)
#   - Container: container_access_type = "private" (browser hits backend proxy)
#   - No versioning, no soft-delete retention, no lifecycle, no change feed
#   - Lifecycle precondition re-checks LRS at plan time

resource "azurerm_storage_account" "images" {
  name                     = module.naming.storage_account_images
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  access_tier              = "Hot"
  min_tls_version          = "TLS1_2"

  # Account-level safety net. Container below is also private, but this
  # blocks any future container drift from publishing data accidentally.
  allow_nested_items_to_be_public = false

  # Connection-string auth is enabled (Phase-4 simplicity). Future phase:
  # set to false and switch to Managed Identity + role assignments.
  shared_access_key_enabled = true

  # Required for the Web App (West Europe) to reach this account over the
  # Azure backbone. No private endpoints (paid feature).
  public_network_access_enabled = true

  tags = module.naming.tags

  # Note: postconditions (which can use `self`) would catch in-place drift,
  # but azurerm provider mutates these fields if they differ from config.
  # Pre-creation guards live at the variable level instead — see the
  # validation rules on backend_storage_backend and the SKU/tier values
  # hardcoded in this resource block. Treat any future edit that introduces
  # a `var.storage_replication_type` etc. as the place to add validations.

  lifecycle {
    # Critical Data Protection — every uploaded product image lives here.
    # Destroy would drop all blobs; replace (e.g. account-tier change) would
    # also recreate the account and lose the data.
    prevent_destroy = true
  }
}

# Private container — no anonymous read. Image bytes reach the browser via
# the backend proxy /api/v1/products/images/file/{key}, which streams the
# blob bytes through the authenticated SDK client. See
# app/products/router.py:stream_image_file.
resource "azurerm_storage_container" "images" {
  name                  = var.azure_storage_container
  storage_account_id    = azurerm_storage_account.images.id
  container_access_type = "private"

  lifecycle {
    # Critical Data Protection — all product images live in this container.
    # The storage-account lifecycle block above also has prevent_destroy,
    # but locking the container independently catches the case where someone
    # renames or relocates this resource without recreating the account.
    prevent_destroy = true
  }
}

# --- Critical Data Protection: Azure resource locks (CanNotDelete) ----------
#
# Defense-in-depth alongside the prevent_destroy lifecycle blocks above.
# Resource locks live at the Azure ARM layer, so they protect against any
# DELETE attempt regardless of source — Terraform, az CLI, the portal,
# manual scripts. Free service (Resource Manager / Cost Management / Locks
# are always free per CLAUDE.md §3 Allowlist).
#
# Lock level "CanNotDelete" allows reads and updates, blocks DELETE only.
# That means:
#   - Bumping image tags / app_settings: unaffected.
#   - Rotating Postgres admin password: unaffected (UPDATE call).
#   - Rotating Storage Account access keys: unaffected.
#   - Creating/updating containers, blobs, firewall rules: unaffected.
#   - DELETEing the server, database, account, or container: blocked.
#
# Locks at the parent scope inherit to all child resources, so the two
# locks below cover the database (under the server) and the container
# (under the account) too. A second pair of explicit child locks would be
# redundant.
#
# Removing a lock requires editing this config and applying — combined with
# prevent_destroy on the protected resource, an actual destroy requires
# TWO config edits (remove the lock resource AND remove prevent_destroy).
# That is intentional friction. See handoff/SAFE_TASK_RULES.md "Critical
# Data Protection" before ever proposing either edit.

resource "azurerm_management_lock" "postgres_no_delete" {
  name       = "${module.naming.postgres_server}-no-delete"
  scope      = azurerm_postgresql_flexible_server.this.id
  lock_level = "CanNotDelete"
  notes      = "Critical Data Protection. Inherits to azurerm_postgresql_flexible_server_database.app. Remove only with explicit user approval — see handoff/SAFE_TASK_RULES.md."
}

resource "azurerm_management_lock" "storage_no_delete" {
  name       = "${module.naming.storage_account_images}-no-delete"
  scope      = azurerm_storage_account.images.id
  lock_level = "CanNotDelete"
  notes      = "Critical Data Protection. Inherits to azurerm_storage_container.images and all blobs. Remove only with explicit user approval — see handoff/SAFE_TASK_RULES.md."
}
