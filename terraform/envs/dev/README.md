# Phase 1–5 + Security Tasks A/B/C — Frontend, Backend, PostgreSQL & Blob Storage Azure deployment (dev)

Terraform that deploys both Web Apps, a managed PostgreSQL Flexible Server,
and an Azure Blob Storage Account to Azure on the **12-month free tier**:

- **Phase 1** — frontend Web App (`hoso30/art-frontend`) on `asp-art-dev` (F1 Free).
- **Phase 2** — backend Web App (`hoso30/art-backend`) with worker + redis
  sidecars on `asp-art-backend-dev` (F1 Free).
- **Phase 3** — Azure PostgreSQL Flexible Server **B_Standard_B1ms** with
  32 GB storage / 32 GB backup / 7-day retention (12-month free tier).
- **Phase 4** — Azure Storage Account (Standard_LRS, StorageV2, Hot) with
  private container `art-images`. Replaces the MinIO sidecar in Azure;
  MinIO is still used for local docker-compose dev. `STORAGE_BACKEND=azure`
  is the default in deployed envs.
- **Phase 5** — Product image gallery (multiple images per product, clickable
  card → fullscreen lightbox with prev/next/thumbnails/keyboard nav).
  Backend image proxy is backend-agnostic so the same code path serves both
  MinIO (local) and Azure Blob (deployed).
- **Task A** — credentials hardening: SECRET_KEY validation, FastAPI docs
  gated in production, seed credential gate.
- **Task B** — auth-surface hardening: slowapi rate limiting on login,
  OriginCheckMiddleware, non-root backend container.
- **Task C1** — PostgreSQL least-privilege runtime user. Application runtime
  uses `art_app` (CRUD only); `art_admin` is reserved for migrations and
  bootstrap.
- **Task C2a** — Storage Managed Identity. Backend Web App has
  System-Assigned identity granted `Storage Blob Data Contributor` on the
  storage account; backend authenticates via `DefaultAzureCredential`.
- **Task C2b** — shared-key denial. `AZURE_STORAGE_CONNECTION_STRING`
  removed from app_settings; `shared_access_key_enabled = false` on the
  storage account. Provider uses `storage_use_azuread = true` so plans can
  still read storage sub-properties via Entra ID.

Key Vault, ACR, paid monitoring are still out of scope. Cost target while
the 12-month window is open: **$0/month**. After it closes, see "Cost after
free-tier expires" below.

**Live as of latest apply:** `frontend_image_tag = v33`, `backend_image_tag = v36`.

## What gets created

| Resource | Type | Notes |
|---|---|---|
| `rg-art-dev` | `azurerm_resource_group` | Location: West Europe (locked by CLAUDE.md). |
| `asp-art-dev` | `azurerm_service_plan` | Linux, **F1**. Frontend plan. |
| `asp-art-backend-dev` | `azurerm_service_plan` | Linux, **F1**. Backend plan. |
| `app-art-frontend-dev-<suffix>` | `azurerm_linux_web_app` | Frontend, single container, port 3000. |
| `app-art-backend-dev-<suffix>` | `azurerm_linux_web_app` | Backend, multi-container, port 8000. **System-Assigned identity** (Task C2a) granted `Storage Blob Data Contributor` on the storage account. |
| Backend `backend` site container | `azapi_resource` (sitecontainers) | Main — `hoso30/art-backend:v30`. |
| Backend `worker` site container | `azapi_resource` (sitecontainers) | Sidecar — Celery worker + beat. |
| Backend `redis` site container | `azapi_resource` (sitecontainers) | Sidecar — `redis:7-alpine`, internal only. |
| Backend `minio` site container | `azapi_resource` (sitecontainers, **disabled by default**) | Phase 4 swap: replaced by Azure Blob Storage. Set `minio_sidecar_enabled = true` if you want it back. Sidecar binds 9100/9101 to avoid the App Service PHP-FPM 9000 collision. Local docker-compose dev still uses MinIO. |
| `startdevimgsart4242` | `azurerm_storage_account` | **Standard_LRS, StorageV2, Hot tier.** Free 12-month allowance: 5 GB / 20k reads / 10k writes. Public-blob access disabled at account level. **`shared_access_key_enabled = false`** (Task C2b) — shared-key auth blocked at data plane; only Entra ID/Managed Identity tokens accepted. |
| `art-images` | `azurerm_storage_container` | Private container — browser fetches via backend proxy, never directly. Auto-created by the SDK on first request. |
| Role assignment for backend MI | `azurerm_role_assignment` | `Storage Blob Data Contributor` on the storage account scope, principal_id = backend Web App's System-Assigned identity. Gated by `var.enable_storage_role_assignment` (two-stage apply pattern — see "Task C2a two-stage apply" below). |
| `psql-art-dev-<suffix>-no-delete` | `azurerm_management_lock` | **Critical Data Protection.** `CanNotDelete` lock on the Postgres server. Inherits to the database. Free (Resource Manager). Allows reads and updates; blocks DELETE. |
| `startdevimgsart4242-no-delete` | `azurerm_management_lock` | **Critical Data Protection.** `CanNotDelete` lock on the Storage Account. Inherits to the container and all blobs. Free (Resource Manager). |
| `psql-art-dev-<suffix>` | `azurerm_postgresql_flexible_server` | **B1MS**, PG 16, 32 GB storage, 7-day backup, no HA, no geo-redundant. **Region: `var.postgres_location` (default North Europe)** — see "PostgreSQL region exception" below. |
| `art_manufacturing` | `azurerm_postgresql_flexible_server_database` | Application DB on the Flexible Server. UTF8 / en_US.utf8. |
| `AllowAzureServices` | `azurerm_postgresql_flexible_server_firewall_rule` | Magic `0.0.0.0–0.0.0.0` rule = "allow all Azure services". Only opens the Azure backbone, not the public internet. Credentials still required. |
| `DumpClient` | `azurerm_postgresql_flexible_server_firewall_rule` | **Optional, count-gated.** Created only when `var.dump_client_ip` is set (default null = no rule). Single IPv4 address that can reach 5432 for ad-hoc local `pg_dump`. Set in gitignored `terraform.tfvars` only when running `scripts/db/dump-postgres.sh`; remove and re-apply afterward. See `scripts/db/README.md` (Firewall). |
| (in-state) `random_password.postgres_admin` | `random_password` | 24-char URL-safe password. Postgres server admin (`art_admin`). Stored in Terraform state — read via `terraform output`. Used by Alembic migrations and bootstrap. |
| (in-state) `random_password.art_app_db` | `random_password` | 24-char URL-safe password for the runtime `art_app` role (Task C1). Read by `scripts/bootstrap_db_user.py` to set/rotate the role's password on cold start. |

All names are computed by `../../modules/naming` from `project + environment + suffix`.

State is **local**. Remote backend deferred to a later phase.

## Sensitive files — never commit

These three files contain secrets the deployment depends on. All three are listed in `.gitignore`. Verify with `git status` before every commit:

| File | Sensitive content |
|---|---|
| `terraform/envs/dev/.env.terraform` | The four `ARM_*` Service Principal credentials. Anyone with these has full subscription control. Never `cat` into a chat or commit message. |
| `terraform/envs/dev/terraform.tfvars` | `backend_secret_key` (JWT signing key). JWT key compromise = mint admin tokens. Also persists `enable_storage_role_assignment = true`. |
| `terraform/envs/dev/terraform.tfstate` (and `.backup`) | Postgres `art_admin` password, `art_app` runtime password, storage account access keys (still present in the storage resource even with `shared_access_key_enabled = false`). State is **not encrypted at rest** while the backend is local. Treat the file as an offline secret store; if you need to share with a teammate, share over a secure channel and re-evaluate moving to a remote backend with encryption + audit. |

Secret-handling rules:
- Never echo the contents of these files into a chat / commit message / logs.
- Never publish a `terraform output` value without piping through a redaction step or marking it as sensitive.
- The `storage_account_connection_string` output is marked `sensitive` and won't print without `terraform output -raw`. Even with `shared_access_key_enabled = false`, treat it as confidential — it embeds the still-existing storage account access key.
- **Future hardening:** remove the `storage_account_connection_string` output from `outputs.tf` if no workflow needs it.

## Prerequisites

- Terraform `>= 1.5.0` (`terraform version`).
- An Azure Service Principal with **Contributor** at subscription scope **plus** a Storage data-plane role on `azurerm_storage_account.images` (e.g. `Storage Blob Data Reader` or higher). The data-plane role is required because `storage_use_azuread = true` is set on the provider — without it, `terraform plan` 403s on `KeyBasedAuthenticationNotPermitted` while reading `queue_properties` etc. Subscription-scope Owner satisfies this transitively. **Owner (or `User Access Administrator`) was also temporarily required during Task C2a to create the role assignment** (`Microsoft.Authorization/roleAssignments/write`) and remains required if the role assignment ever needs to be recreated; otherwise Contributor + the data-plane role is enough for steady-state operations.
- A globally-unique value for `suffix` (re-used across both Web App hostnames AND the Postgres server FQDN).
- The subscription must NOT already have a free-tier-claimed PostgreSQL Flexible Server. The Azure 12-month free tier allows **one** eligible Flexible Server per subscription — a second one starts billing at full B1MS rate immediately.

## Providers

Three providers — all authenticate from the same `ARM_*` env vars in `.env.terraform`:

| Provider | Why |
|---|---|
| `hashicorp/azurerm ~> 4.0` | Resource group, App Service Plans, Linux Web Apps, PostgreSQL Flexible Server, Storage Account/container, role assignments, locks. **Configured with `storage_use_azuread = true`** (Task C2b) so plans can read storage account data-plane sub-properties via Entra ID after `shared_access_key_enabled = false`. |
| `Azure/azapi ~> 2.0` | Microsoft.Web/sites/sitecontainers (sidecar containers). azurerm 4.70 doesn't yet expose a native resource for site containers. |
| `hashicorp/random ~> 3.6` | Generates the Postgres admin password and the `art_app` runtime role password at apply time. No Azure API calls. |

`terraform init -upgrade` downloads the random provider on first run after the
Phase 3 update.

## Setup

The azurerm provider reads `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`,
`ARM_SUBSCRIPTION_ID`, and `ARM_TENANT_ID` from the environment.

```bash
cd terraform/envs/dev

# 1. Create the gitignored env file from the example.
cp .env.terraform.example .env.terraform
# Edit .env.terraform — paste the four real Service Principal values.

# 2. Create the gitignored tfvars from the example.
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — at minimum replace REPLACE_ME in `suffix`.

# 3. Source the env file into the current shell.
source .env.terraform

# 4. Init / fmt / validate / plan / apply.
#    -upgrade picks up the new `random` provider on first Phase 3 run.
terraform init -upgrade
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

`source .env.terraform` only affects the current shell. New terminal? Re-source.

First-time `apply` for Phase 3 takes **~5–8 minutes** — Azure provisions the
Postgres server (3–6 min) before the backend starts pulling images.

## Values you MUST edit in `terraform.tfvars`

| Variable | Why |
|---|---|
| `suffix` | Globally-unique tail of both Web App hostnames AND the Postgres FQDN. Replace `REPLACE_ME` with 4–8 lowercase letters/digits. |

Optional, with sensible defaults:

| Variable | Default | When to change |
|---|---|---|
| `frontend_image_tag` | `v24` (default in `variables.tf`); **dev tfvars currently sets `v33`** | Bump when you publish a new frontend image. **Never set to `v13`, `v21`, `v22`, or `v23`** — validation block in `variables.tf` rejects them. v13: failed migration 009; v21: dev-mode build crashed on Tailwind PostCSS; v22/v23: MSYS-mangled `NEXT_PUBLIC_API_URL` poisoned every client-side fetch. See `handoff/KNOWN_RISKS.md` and `handoff/ROLLBACK_NOTES.md`. |
| `backend_image_tag` | `v30` (default in `variables.tf`); **dev tfvars currently sets `v36`** | Bump when you publish a new backend image. **Never set to `v13`, `v26`, or `v27`** — validation in `variables.tf` rejects them. v36 is the current live tag (bulk / series production batch creation, no migration). v35 added the RBAC five-role authorization matrix (migration `012_extend_user_roles`); v34 added per-order sales report; v33 added per-customer sales report; v32 added partial production batch completion; v31 added stock-aware orders dropdown; v30 covered Tasks C1/C2a/C2b. v25–v29 are intermediate retired tags; v26/v27 contained the slowapi rate-limiter bugs. |
| `enable_storage_role_assignment` | `false` | Two-stage apply gate for the backend MI's `Storage Blob Data Contributor` role (Task C2a). Default `false` keeps the role assignment OUT of fresh applies so the planner doesn't fail on `identity[0]` being null when adding identity to an existing Web App. The dev tfvars sets this to `true` post-bootstrap to keep the role assignment in state. See "Task C2a two-stage apply" below. |
| `backend_enabled` | `true` | Set `false` to stop the backend without destroying it (zero CPU, $0). |
| `worker_sidecar_enabled` | `true` | Set `false` if you want backend without Celery (skips worker/beat). |
| `redis_sidecar_enabled` | `true` | Set `false` if you bring your own broker. |
| `minio_sidecar_enabled` | `false` | Phase 4 swap: replaced by Azure Blob Storage. The sitecontainer resource is still defined in `main.tf` for local-dev parity but is disabled by default. Local docker-compose dev still uses MinIO. Don't set this to `true` in a deployed env without a strong reason — the sidecar collides with App Service's PHP-FPM port 9000 unless rebound to 9100/9101. |
| `backend_secret_key` | placeholder | Replace before any real authentication test. |
| `backend_storage_backend` | `azure` | Default for deployed envs (Phase 4). The Azure Blob adapter (`backend/app/storage/azure_adapter.py`) is implemented and proxies bytes through the backend `/api/v1/products/images/file/{key}` endpoint. Set to `minio` only if you re-enable the MinIO sidecar. |

DO NOT set in tfvars (these are computed in `main.tf`):

| Setting | Source |
|---|---|
| `DATABASE_URL` (asyncpg, runtime) | Computed from `art_app` user + `random_password.art_app_db.result` + Postgres FQDN + `?ssl=require`. **Runtime DB user is `art_app` (least-privilege, Task C1)** — CRUD only, no DDL. |
| `DATABASE_URL_SYNC` (psycopg2, migrations + bootstrap) | Computed from `var.postgres_admin_user` (`art_admin`) + `random_password.postgres_admin.result` + Postgres FQDN + `?sslmode=require`. Used by Alembic and `scripts/bootstrap_db_user.py` only. |
| `ART_APP_DB_PASSWORD` | `random_password.art_app_db.result` — read by the bootstrap script to set/rotate the `art_app` role's password. |
| Postgres admin password | Auto-generated by `random_password.postgres_admin`. Sensitive — read with `terraform output -raw postgres_admin_password`. |
| `art_app` runtime password | Auto-generated by `random_password.art_app_db`. Sensitive — read with `terraform output -raw postgres_app_password`. |
| `AZURE_STORAGE_ACCOUNT_URL` | `azurerm_storage_account.images.primary_blob_endpoint`. Drives Managed Identity auth in the backend image v30+. |
| `AZURE_STORAGE_CONTAINER` | `azurerm_storage_container.images.name`. |

Postgres free-tier overrides (defaults already match the free-tier shape; the
validation rules in `variables.tf` will reject anything off-path):

| Variable | Default | Free-tier rule |
|---|---|---|
| `postgres_version` | `16` | Free supports 11–17. |
| `postgres_sku_name` | `B_Standard_B1ms` | Only B1MS is allowed by validation. |
| `postgres_storage_mb` | `32768` (32 GB) | Validation caps at 32 GB. |
| `postgres_backup_retention_days` | `7` | 7–35 allowed (Azure platform rule). |
| `postgres_admin_user` | `art_admin` | **Migrations + bootstrap only** (Task C1). The application runtime uses `art_app` (least-privilege). Cannot be `admin`/`administrator`/`public`/`root` or start with `azure_`/`pg_`. |
| `postgres_database_name` | `art_manufacturing` | Free choice. |
| `postgres_location` | `North Europe` | Region exception (see below). Only the Postgres server uses this. |

## PostgreSQL region exception — why Postgres is in North Europe and everything else in West Europe

CLAUDE.md hard rule says all Azure resources must be in West Europe. The first attempt at Phase 3 hit:

```
Status: "LocationIsOfferRestricted"
Message: "Subscriptions are restricted from provisioning in location 'westeurope'."
Aka: https://aka.ms/postgres-request-quota-increase
```

Azure restricts PostgreSQL Flexible Server provisioning in popular regions for many subscription types — trial, Visual Studio, Azure-for-Students, MOSP. Other resource types in West Europe were unaffected; only Postgres was blocked.

To unblock the deployment without abandoning Postgres or Phase 3, the project takes a narrow exception (documented in CLAUDE.md):

- **Only `azurerm_postgresql_flexible_server.this.location`** uses `var.postgres_location` (default `"North Europe"`).
- The resource group, both App Service Plans, both Web Apps, and all three sidecar containers stay in **West Europe**.
- The RG itself remains in West Europe — RG location is metadata; child resources are free to live in any region within the same RG.
- North Europe is ~10 ms RTT from West Europe and is on the same free-tier B1MS offer.

Cross-region egress between Web App (West Europe) and Postgres (North Europe) is inside the always-free 100 GB outbound allowance for any realistic dev workload, so the $0 target is preserved.

**To restore single-region** when the West Europe block is lifted (quota approved or subscription upgraded):

1. Set `postgres_location = "West Europe"` in `terraform.tfvars` (or remove the override — but the default is North Europe, so an explicit override is needed).
2. `pg_dump` if there is data to preserve (the recreate is destructive).
3. `terraform apply` — the server is destroyed and recreated in West Europe.
4. Restore from the dump if applicable.

## Outputs

After `apply`, Terraform prints (run `terraform output` to re-print):

| Output | What it is |
|---|---|
| `frontend_url` | Public HTTPS URL of the frontend |
| `backend_url` | Public HTTPS URL of the backend |
| `backend_default_hostname` | Backend hostname (no scheme) |
| `backend_image` | The `image:tag` configured for backend + worker sidecars |
| `backend_enabled_state` | `running` or `stopped` |
| `worker_sidecar_enabled` / `redis_sidecar_enabled` | Bool, mirrors input |
| `postgres_server_name` | `psql-art-dev-<suffix>` |
| `postgres_fqdn` | `psql-art-dev-<suffix>.postgres.database.azure.com` |
| `postgres_database` | `art_manufacturing` |
| `postgres_admin_user` | `art_admin` (migrations + bootstrap only — runtime is `art_app`) |
| `postgres_admin_password` | **sensitive** — read with `terraform output -raw postgres_admin_password` |
| `postgres_app_password` | **sensitive** — `art_app` runtime password (Task C1). Read with `terraform output -raw postgres_app_password`. |
| `storage_account_name` | `startdevimgsart4242` |
| `storage_account_primary_blob_endpoint` | `https://startdevimgsart4242.blob.core.windows.net/` — populated into the backend's `AZURE_STORAGE_ACCOUNT_URL` app setting. |
| `storage_account_connection_string` | **sensitive** — connection string. Although `shared_access_key_enabled = false` blocks key auth at the data plane, this string still embeds the storage account access key. Treat as confidential. **Future hardening: remove this output entirely** if no workflow needs it (currently kept for debugging). |
| `names_preview` | Map of all computed names |

### How to retrieve the generated PostgreSQL passwords

```bash
# Admin password — used by Alembic migrations + bootstrap_db_user.py only.
terraform output -raw postgres_admin_password

# Runtime art_app password — used by the application at runtime (Task C1).
terraform output -raw postgres_app_password

# Connect as the admin (DDL-capable; use sparingly):
PGPASSWORD="$(terraform output -raw postgres_admin_password)" \
psql "host=$(terraform output -raw postgres_fqdn) \
      port=5432 \
      user=$(terraform output -raw postgres_admin_user) \
      dbname=$(terraform output -raw postgres_database) \
      sslmode=require"

# Connect as art_app (CRUD only; what the backend uses):
PGPASSWORD="$(terraform output -raw postgres_app_password)" \
psql "host=$(terraform output -raw postgres_fqdn) \
      port=5432 \
      user=art_app \
      dbname=$(terraform output -raw postgres_database) \
      sslmode=require"
```

Both passwords are in `terraform.tfstate` — keep that file out of git (it's
already gitignored). **The state file is sensitive: it also contains the
storage account access keys (used to compute `storage_account_connection_string`,
even though shared-key auth is disabled at the data plane).** For team
workflows, move state to an Azure Storage backend with blob lease locking
before sharing.

Rotation:
- Admin password: `terraform taint random_password.postgres_admin && terraform apply`. Regenerates the admin password, updates `DATABASE_URL_SYNC`, and the backend will restart. Alembic + bootstrap on next cold start use the new password.
- `art_app` password: `terraform taint random_password.art_app_db && terraform apply`. The bootstrap script (`scripts/bootstrap_db_user.py`) `ALTER ROLE art_app WITH PASSWORD …` to match `ART_APP_DB_PASSWORD` on every cold start, so the rotation is idempotent and self-applies on restart.

## Task C2a two-stage apply — `enable_storage_role_assignment`

When the backend Web App's System-Assigned identity is being added to an **existing** resource (as it was when C2a first applied), Terraform's planner sees `azurerm_linux_web_app.backend.identity[0]` as null in the pre-apply state and refuses the role assignment with `Missing required argument: principal_id`. A `count = length(...) > 0` guard does not fix this — the planner resolves the principal_id expression eagerly.

The fix is the gate variable `enable_storage_role_assignment`:

- **Default `false`** (in `variables.tf`). On a from-scratch apply against an existing Web App, the first run only creates the identity; the role assignment is skipped.
- **Set to `true`** in the gitignored `terraform.tfvars` after the first apply succeeds. The next plan/apply creates `azurerm_role_assignment.backend_blob_data_contributor[0]` (1 add). After both applies, the role assignment is permanent.

For a from-scratch apply where the Web App is being CREATED with identity (greenfield env), `enable_storage_role_assignment = true` from the start works in a single apply — `identity[0].principal_id` is correctly marked "known after apply" when the parent resource is in the plan-add set.

The dev env's `terraform.tfvars` already has `enable_storage_role_assignment = true`. **Do not remove it** or the next apply will plan a destroy of the role assignment.

## Critical Data Protection — PostgreSQL & Storage are double-locked

PostgreSQL and Azure Blob Storage hold all application data and are protected by two layers:

1. **Lifecycle `prevent_destroy = true`** on `azurerm_postgresql_flexible_server.this`, `azurerm_postgresql_flexible_server_database.app`, `azurerm_storage_account.images`, `azurerm_storage_container.images`. Any plan with destroy/replace for these resources fails before apply.
2. **Azure resource locks** (`CanNotDelete`) on the Postgres server and the Storage Account, declared as `azurerm_management_lock.postgres_no_delete` and `azurerm_management_lock.storage_no_delete`. Locks inherit to child resources (database, container, blobs) so two locks cover all four. Free (Resource Manager). They block DELETE via any path — portal, `az` CLI, ARM API, Terraform itself — and allow reads and updates so image-tag bumps and app-setting changes are unaffected.

The expected steady-state plan for an image-tag bump or app-setting change is **`N to change, 0 to add, 0 to destroy`**, with the four protected resources not appearing at all. Anything else means stop and inspect — see `handoff/SAFE_TASK_RULES.md` "Critical Data Protection".

The only legitimate destroy/replace path is the documented "PostgreSQL → West Europe" recreate when the `LocationIsOfferRestricted` block lifts. Sequence: `pg_dump` → comment out the lock → comment out `prevent_destroy` → apply → `pg_restore` → restore both layers → apply. Each step is its own user approval. Full procedure in `handoff/SAFE_TASK_RULES.md`.

## Known limitations

These are **not Terraform bugs** — they're consequences of scope.

### 1. New frontend image required when `INTERNAL_API_URL` changes

Next.js 14 standalone freezes the `/api/*` rewrite destination into
`routes-manifest.json` at **frontend build time** (driven by the
`INTERNAL_API_URL` build-arg). Setting `INTERNAL_API_URL` as an Azure App
Setting at runtime has **no effect** — Terraform still sets it on the Web
App so it's correct after a future rebuild, but rolling out a backend URL
change requires a fresh frontend image.

Today both Web Apps are stable and the build-arg points at the live
backend hostname (`https://app-art-backend-dev-art4242.azurewebsites.net`).
You only need to rebuild the frontend image when:

- the backend hostname changes (e.g. you change `var.suffix`), or
- you change a `NEXT_PUBLIC_*` value, or
- you change anything in `frontend/src/`.

Reference build command (run from Git Bash on Windows — `MSYS_NO_PATHCONV=1`
is **mandatory**, otherwise `/api/v1` becomes `C:/Program Files/Git/api/v1`
and every browser-side fetch in the deployed bundle throws TypeError; this
is exactly why v22 and v23 are blacklisted):

```bash
MSYS_NO_PATHCONV=1 docker build -f frontend/Dockerfile.azure \
  --build-arg "INTERNAL_API_URL=$(terraform output -raw backend_url)" \
  --build-arg "NEXT_PUBLIC_API_URL=/api/v1" \
  --build-arg "NEXT_PUBLIC_APP_NAME=ART Manufacturing" \
  -t hoso30/art-frontend:vN ./frontend

# Verify no MSYS poisoning in the built image
docker run --rm hoso30/art-frontend:vN sh -c \
  'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
# Empty output required.

docker push hoso30/art-frontend:vN
# Bump frontend_image_tag in terraform.tfvars, then terraform plan + apply.
```

See `CLAUDE.md` "Building Docker images on Windows / Git Bash" for the
full ruleset.

### 2. F1 limits apply to both plans

Each F1 plan has independently:

- 60 CPU min/day (frontend plan; or shared across backend + worker + redis on the backend plan)
- 1 GB RAM total
- No `always_on` — apps cold-start after ~20 min idle. With Postgres in
  place alembic now succeeds in seconds, but cold-starts still add 30–60 s
  to the first request after idle.
- Celery Beat (in the worker sidecar) only fires while the worker process is
  awake. The daily 06:00 UTC stock check will NOT run reliably without
  `always_on`.

### 3. B1MS Burstable connection cap

Azure caps B1MS at ~50 connections. Backend uses SQLAlchemy
`pool_size=20, max_overflow=10` per uvicorn worker, and uvicorn runs with
`--workers 2`. Worst case = 60 connections. Mitigations if exhausted:

- Lower `pool_size` to 10 in `backend/app/database.py`, or
- Drop uvicorn to `--workers 1` in `backend/entrypoint.sh`, or
- (paid) bump SKU to B2s.

Not blocking for dev usage; flag if `psycopg2.OperationalError: FATAL: too many
connections` shows up in logs.

## Expected `terraform plan` summary

For a steady-state environment (Phase 1–5 + Tasks A/B/C all applied), `terraform plan` returns:

```
No changes. Your infrastructure matches the configuration.
```

For a typical image-tag bump (e.g. publishing a new backend tag and updating `backend_image_tag` in tfvars):

```
Plan: 0 to add, 3 to change, 0 to destroy.

  ~ azurerm_linux_web_app.backend  (image tag in app_settings, if referenced there)
  ~ azapi_resource.backend_main    (image vN → vN+1)
  ~ azapi_resource.backend_worker  (image vN → vN+1)
```

For a tfvars edit that touches only an app setting:

```
Plan: 0 to add, 1 to change, 0 to destroy.

  ~ azurerm_linux_web_app.backend  (single app_settings entry changed)
```

**Hard rule — none of the protected resources should appear in any plan, ever**, except during the documented "PostgreSQL → West Europe" recreate:

- `azurerm_postgresql_flexible_server.this`
- `azurerm_postgresql_flexible_server_database.app`
- `azurerm_storage_account.images`
- `azurerm_storage_container.images`
- `azurerm_management_lock.postgres_no_delete`
- `azurerm_management_lock.storage_no_delete`

If any of those show `-/+` (replacement) or `- destroy`, **stop and surface to the user**. See `handoff/SAFE_TASK_RULES.md` "Critical Data Protection".

### Special-case plans

- **Initial Phase 3 apply (Postgres bootstrap)** — `4 to add, 1 to change, 0 to destroy`: `random_password.postgres_admin`, `azurerm_postgresql_flexible_server.this`, `azurerm_postgresql_flexible_server_database.app`, `azurerm_postgresql_flexible_server_firewall_rule.allow_azure_services`; backend Web App's `app_settings` populated with the new `DATABASE_URL`/`DATABASE_URL_SYNC`/`ART_APP_DB_PASSWORD`.
- **Task C2a stage 1** (identity + URL + role-assignment-disabled) — `0 to add, 3 to change, 0 to destroy`: identity block on backend, `AZURE_STORAGE_ACCOUNT_URL` setting, image bump.
- **Task C2a stage 2** (`enable_storage_role_assignment = true`) — `1 to add, 0 to change, 0 to destroy`: `azurerm_role_assignment.backend_blob_data_contributor[0]`.
- **Task C2b** (remove connection string + flip shared-key) — `0 to add, 2 to change, 0 to destroy`: backend `app_settings` removes `AZURE_STORAGE_CONNECTION_STRING`; `azurerm_storage_account.images.shared_access_key_enabled true → false`. **Note**: the storage flip will fail the post-modify refresh unless `provider "azurerm" { storage_use_azuread = true }` is set first — see `KNOWN_RISKS.md`.

Critical:
- The `moved` block from Phase 2 ensures the live frontend is **not** destroyed.
- `azurerm_postgresql_flexible_server.this` takes 3–6 minutes to provision; this is the slow step.
- The lifecycle `precondition` aborts the plan if `postgres_sku_name` is anything other than `B_Standard_B1ms`.

## Expected Azure behavior after apply

- **Frontend** (`https://app-art-frontend-dev-<suffix>.azurewebsites.net`) — homepage / catalog render. `/api/*` calls still go to `localhost:8000` until the image is rebuilt (see limitation #1).
- **Backend** (`https://app-art-backend-dev-<suffix>.azurewebsites.net`) — first cold start is 2–5 min (Azure pulls images, alembic runs migrations against real Postgres, uvicorn boots). Then `GET /health` returns 200.
- **Postgres** — visible in the portal under **Resource groups → rg-art-dev → psql-art-dev-<suffix>**. Backups appear after ~24 h (7-day retention). The `art_manufacturing` DB shows the schema after first `alembic upgrade head` succeeds.

## How to check PostgreSQL in the Azure Portal

1. Portal → **Resource groups** → `rg-art-dev` → click `psql-art-dev-<suffix>`.
2. **Overview** tab — confirm:
   - **Status: Available** (not "Stopped" or "Updating").
   - **Compute + storage: Burstable, Standard_B1ms** (NOT B2s, NOT GP).
   - **Storage: 32 GB**.
   - **Backup retention: 7 days**, **Geo-redundant backup: Disabled**.
   - **High availability: Disabled**.
3. **Networking** → **Public access** is enabled, with one firewall rule
   `AllowAzureServices` (start/end = `0.0.0.0`).
4. **Databases** → `art_manufacturing` is listed. Click it to confirm the schema
   appears (after backend's first successful alembic run).
5. **Cost analysis** under the subscription should show `$0` for this server
   while the 12-month free tier is active. After expiry, B1MS bills ~$15/mo.

## How to check backend logs

```bash
# Tail all containers in the backend Web App
az webapp log tail \
  -g $(terraform output -raw resource_group_name) \
  -n $(terraform output -raw backend_web_app_name)
```

Or in the portal: **App Services → `app-art-backend-dev-<suffix>` → Monitoring → Log stream**.

To inspect a specific sidecar (backend / worker / redis):
**App Services → backend Web App → Deployment Center → Containers** — click the
container row → "Logs" tab.

## How to confirm Alembic succeeded

In the backend log stream, look for the entrypoint sequence:

```
[entrypoint] waiting for database...
[entrypoint] running: alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, ...
...
INFO  [alembic.runtime.migration] Running upgrade 010_xxx -> 011_xxx, ...
[entrypoint] migrations applied. starting uvicorn.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Or query Postgres directly:

```bash
PGPASSWORD="$(terraform output -raw postgres_admin_password)" \
psql "host=$(terraform output -raw postgres_fqdn) \
      port=5432 \
      user=$(terraform output -raw postgres_admin_user) \
      dbname=$(terraform output -raw postgres_database) \
      sslmode=require" \
      -c "SELECT version_num FROM alembic_version;"
```

The output should show the latest revision ID (matches `backend/alembic/versions/`'s
highest-numbered file). If `alembic_version` doesn't exist, alembic never
finished — check the entrypoint log for the failure reason (network, auth,
schema mismatch).

Quick health check from any shell that can reach the Web App:

```bash
curl -i "$(terraform output -raw backend_url)/health"
# → HTTP/2 200
```

## Test what works

After `apply` against the current image tags (frontend v24, backend v30):

1. **Frontend homepage** — open `frontend_url`. Renders. No build errors.
2. **Backend health** — `curl -i $(terraform output -raw backend_url)/health` → 200.
3. **Public products endpoint** — `curl -i "$(terraform output -raw backend_url)/api/v1/products/public?limit=8"` → 200 with `{items:[…], total, page, limit}`.
4. **Frontend → backend API call via the browser** — works. Log in as admin, hit `/dashboard/production`, click "Ստեղծել արտադրություն"; the product dropdown populates with all products.
5. **Product image upload + display** — admin: `/dashboard/products/<id>` → upload a JPG/PNG/WebP. The image lands in Azure Blob (`art-images` container) and the gallery shows it via the backend proxy `/api/v1/products/images/file/{key}`.

To re-verify the deployed bundle is clean (no MSYS poisoning of client-side fetches):

```bash
CHUNK=$(curl -s "$(terraform output -raw frontend_url)/dashboard/production" \
  | grep -oE '/_next/static/chunks/app/dashboard/production/page-[a-f0-9]+\.js' | head -1)
curl -s "$(terraform output -raw frontend_url)$CHUNK" | grep -c "C:/Program Files/Git"
# Must be 0.
```

## How to keep this inside $0

- **Don't add a second free-tier-eligible Postgres in the same subscription.** Azure auto-bills the second one at full B1MS rate. Verify with `az postgres flexible-server list -o table`.
- **Keep `postgres_sku_name = "B_Standard_B1ms"`.** The validation in `variables.tf` and the lifecycle `precondition` in `main.tf` will refuse anything else, but a manual portal change can override Terraform between applies.
- **Keep `postgres_storage_mb <= 32768`.** Above 32 GB, storage bills at ~$0.115/GB/month. Auto-grow is intentionally OFF — writes will fail rather than silently slip into paid storage.
- **Keep `geo_redundant_backup_enabled = false`** and `backup_retention_days <= 7`. Anything above 7 days × 32 GB starts incurring backup-storage charges.
- **Keep both App Service Plans on F1.** B1 starts billing at ~$13/month/plan.
- **Don't add a Storage Account, ACR, Key Vault, or Application Insights without an explicit Cost Impact approval.** All have free tiers, but combinations and overage shifts the bill quickly.
- **Watch the 60 CPU min/day F1 quota.** Backend's alembic loop won't burn it now (Postgres is real), but a runaway worker task can. Stop the backend with `backend_enabled = false` if you see "App Service plan exceeded its quota" 403s.
- **Set a billing alert.** Subscription → Cost Management → Budgets → create a budget at $1/month with email alerts. Anything above $0 is a regression.

### Cost after the 12-month free tier expires

The free-tier window starts at **subscription creation**, not server creation.
After it closes, B1MS bills automatically — roughly:

- B1MS compute: ~$13/month
- 32 GB SSD storage: ~$3.70/month
- 32 GB backup (LRS, 7-day): free portion gone — ~$3/month overflow

Total: **~$20/month** for the Postgres server alone, on top of any other paid
resources. Mitigations before expiry:

- `terraform destroy` on Postgres (loses data — back up `pg_dump` first).
- Migrate the data into the SQLite test DB used by `pytest` and run dev locally.
- Move to a different free DB tier (Supabase, Neon free, etc. — not Azure).

A reminder is in `CLAUDE.md` § Azure Free Resources Allowlist; check the
Azure portal under **Subscriptions → Overview → Offer details** for the
exact subscription start date.

## Destroy

```bash
terraform destroy
```

Deletes both Web Apps, both plans, the Postgres server, and the resource
group. **The Postgres server is destroyed — all data is lost.** If you want
to keep the data, run `pg_dump` first.

Local state file remains; remove with `rm -f terraform.tfstate
terraform.tfstate.backup` for a clean slate.

## How to stop the backend without destroying anything

```bash
# In terraform.tfvars:
backend_enabled = false
terraform apply
```

Backend Web App goes to "Stopped" state. Containers stop. Postgres server
keeps running (still free during the 12-month window). Frontend keeps
running. Set back to `true` to resume.

## What is NOT yet deployed (next-phase candidates, all separately approved)

- **Key Vault** for `SECRET_KEY` and DB passwords (currently in `terraform.tfvars` and `terraform.tfstate` respectively — both gitignored, both treat as secrets).
- **Application Insights / Log Analytics** for proper observability.
- **Remote Terraform state** (Azure Storage backend with blob lease locking — would also encrypt state at rest with audit trail).
- **CI/CD pipeline.**
- **`int` / `prod` environments.**
- **Remove `storage_account_connection_string` output** — no longer needed by any workflow now that MI is the only auth path. Currently kept for break-glass debugging.

Each of these is a separate Cost-Impact-gated proposal per CLAUDE.md.

## What is now done (was previously listed as not-yet)

- ✅ Frontend image rebuild with absolute `INTERNAL_API_URL` baked in — done at v20 baseline; current live tag is `v24`.
- ✅ Storage Account / Blob for product image uploads — done at Phase 4. Replaces MinIO in deployed envs. `art-images` container, Standard_LRS Hot, private. Adapter at `backend/app/storage/azure_adapter.py`.
- ✅ Backend image proxy is backend-agnostic (works with both MinIO and Azure Blob) — first delivered in `art-backend:v21`, current live tag is `v30`.
- ✅ Multi-image product gallery (clickable card → fullscreen lightbox with prev/next/thumbnails/keyboard nav) — `art-frontend:v20+`.
- ✅ Production modal product dropdown — works on `art-frontend:v24`. v22/v23 had MSYS-poisoned URLs and are blacklisted.
- ✅ **Critical-credentials hardening (Task A)** — backend image v25+. SECRET_KEY validator refuses placeholder/short keys in production, FastAPI docs gated in production, seed credentials gated by `ENABLE_SEED_DATA` + non-default password.
- ✅ **Auth-surface hardening (Task B)** — backend image v28+. slowapi rate limit (5/min on login, 20/min on refresh) with XFF-aware client-IP key (port-stripped for Azure App Service); OriginCheckMiddleware blocks unsafe methods with bad/missing Origin/Referer; backend container runs as non-root `app:1001`.
- ✅ **Postgres least-privilege runtime user (Task C1)** — backend image v29+. `scripts/bootstrap_db_user.py` runs from `entrypoint.sh` after Alembic and before uvicorn; idempotently creates `art_app`, sets/rotates its password from `ART_APP_DB_PASSWORD`, and re-grants `CONNECT/USAGE/CRUD` on schema `public` + default privileges. Runtime `DATABASE_URL` connects as `art_app`. `DATABASE_URL_SYNC` keeps the admin so Alembic + bootstrap retain DDL + role-management rights.
- ✅ **Storage Managed Identity (Task C2a)** — backend image v30. Backend Web App has System-Assigned identity granted `Storage Blob Data Contributor` on the storage account; adapter uses `BlobServiceClient(account_url, DefaultAzureCredential())` when `AZURE_STORAGE_ACCOUNT_URL` is set.
- ✅ **Storage shared-key denial (Task C2b)** — `AZURE_STORAGE_CONNECTION_STRING` removed from `app_settings`; `shared_access_key_enabled = false` on the storage account. Provider configured with `storage_use_azuread = true` so plans can read storage data-plane sub-properties via Entra ID.
