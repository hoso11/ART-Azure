# Azure deployment — current state

This document describes the **live, working Azure deployment** as managed by Terraform in `terraform/envs/dev/`. It supersedes earlier revisions of this file that described the obsolete single-Web-App-with-five-sidecars topology in Germany West Central.

## Current architecture

```
Public internet
      │
      │  HTTPS
      ▼
┌─────────────────────────────────────────────────────────┐
│  Azure                                                  │
│  Resource group: rg-art-dev   (West Europe)             │
│                                                         │
│  ┌──────────────────────────┐                           │
│  │ asp-art-dev (F1 Free)    │                           │
│  │  └── app-art-frontend-…  │  Next.js 14 standalone    │
│  │      port 3000           │  (single container)       │
│  └──────────────────────────┘                           │
│                                                         │
│  ┌──────────────────────────┐                           │
│  │ asp-art-backend-dev (F1) │                           │
│  │  └── app-art-backend-…   │  FastAPI + Alembic        │
│  │      port 8000 (main)    │                           │
│  │      ├── worker sidecar  │  Celery worker + beat     │
│  │      └── redis sidecar   │  redis:7-alpine, internal │
│  └──────────────────────────┘                           │
│                                                         │
│  psql-art-dev-art4242                                   │
│   Azure Database for PostgreSQL Flexible Server         │
│   B_Standard_B1ms, PG 16, 32 GB, North Europe (*)       │
│                                                         │
│  startdevimgsart4242                                    │
│   Azure Storage Account (Standard_LRS, StorageV2, Hot)  │
│   Container: art-images (private)                       │
└─────────────────────────────────────────────────────────┘

(*) PostgreSQL exception: `LocationIsOfferRestricted` on the
subscription forced the Flexible Server into North Europe. Every
other resource is in West Europe. See CLAUDE.md "PostgreSQL only"
exception clause.
```

### Request flow

- Browser → `https://app-art-frontend-dev-art4242.azurewebsites.net/…` → frontend Web App (Next.js, port 3000).
- Browser → `/api/v1/*` → frontend's Next.js standalone server applies the `next.config.js` rewrite → `https://app-art-backend-dev-art4242.azurewebsites.net/api/v1/*` (separate backend Web App). The destination is **baked into `routes-manifest.json` at frontend image build time** via `INTERNAL_API_URL` — changing it requires a frontend rebuild + push + tag bump.
- Backend → PostgreSQL Flexible Server (`psql-art-dev-art4242.postgres.database.azure.com:5432`, `sslmode=require`).
- Backend → Redis sidecar (`localhost:6379`, shared network namespace inside the backend Web App).
- Backend → Azure Blob Storage (`startdevimgsart4242.blob.core.windows.net`, container `art-images`, private). Browsers never reach Blob directly — product image bytes are streamed through the backend `/api/v1/products/images/file/{key}` proxy via `storage.download_file()`.
- Worker sidecar → Redis broker, PostgreSQL, Blob storage. Same network namespace as backend.

### What is _not_ in the deployment (intentionally)

- **No nginx.** The Azure platform terminates TLS and the Next.js rewrite handles the `/api/*` → backend hop. nginx would only add a hop.
- **No Postgres sidecar.** Replaced by Azure Database for PostgreSQL Flexible Server in Phase 3.
- **No MinIO sidecar in Azure.** Replaced by Azure Blob Storage in Phase 4. The MinIO sitecontainer resource is still defined in `main.tf` for local-dev parity but defaults to `minio_sidecar_enabled = false`. MinIO remains the **local docker-compose** backend only — never enable it in deployed envs.
- **No connection-string auth to Blob.** Removed in Task C2b. The backend authenticates via System-Assigned Managed Identity → "Storage Blob Data Contributor" on the storage account. `shared_access_key_enabled = false` on the storage account locks shared keys at the data plane.
- **No Application Insights / Log Analytics.** Logs available via portal Log Stream and Kudu only.
- **No Key Vault.** PostgreSQL admin password and storage connection string live in `terraform.tfstate` (gitignored, sensitive — see "Sensitive files" below). `SECRET_KEY` lives in `terraform/envs/dev/terraform.tfvars` (gitignored).
- **No CI/CD.** Image builds and `terraform apply` are run from a developer workstation.

## Image registry

Public Docker Hub under the `hoso30` namespace.

- `hoso30/art-frontend:TAG` — built from `frontend/Dockerfile.azure` (multi-stage: `deps → build → runtime`, ships `node server.js` from `.next/standalone`).
- `hoso30/art-backend:TAG` — built from `backend/Dockerfile`. Reused by the worker sidecar with a different startup command — no separate worker image.

Image tag history (relevant):

| Tag | Status | Notes |
|---|---|---|
| `art-backend:v13` | **Forbidden** | Failed migration `009`; `backend/entrypoint.sh` whitelist exists to recover from it. See `handoff/KNOWN_RISKS.md` #2. |
| `art-backend:v20` | Retired | Pre-Azure-Blob baseline. |
| `art-backend:v21` | Retired | Backend-agnostic image proxy. |
| `art-backend:v25` | Retired | Task A — credentials hardening (SECRET_KEY validation, FastAPI docs gated in production, seed credential gate). |
| `art-backend:v26` | **Forbidden** | slowapi `headers_enabled=True` + dict-return endpoints raised inside `_inject_headers`, short-circuiting the rate limiter. |
| `art-backend:v27` | **Forbidden** | Missing XFF port-strip; Azure App Service prepended ephemeral source ports to each XFF entry, so every request landed in a fresh rate-limit bucket. |
| `art-backend:v28` | Retired | Task B — auth-surface hardening (slowapi 5/min login, OriginCheckMiddleware, non-root container). |
| `art-backend:v29` | Retired | Task C1 — least-privilege Postgres runtime user `art_app` via `scripts/bootstrap_db_user.py`. |
| `art-backend:v30` | Retired | Task C2a/C2b — Azure Blob via Managed Identity. Adapter constructs `BlobServiceClient(account_url, DefaultAzureCredential())` when `AZURE_STORAGE_ACCOUNT_URL` is set; falls back to connection string only if it isn't (no longer used in Azure). Adds `azure-identity==1.19.0` dep. |
| `art-backend:v31` | Retired | Orders list dropdown enforces stock-aware status options (no `Ավարտված` selectable when stock is short). |
| `art-backend:v32` | Retired | Stock-based production batches accept partial completion: `/complete` is now a delta over the cumulative `good_quantity` / `damaged_quantity`; emits `production.batch_progress` on partials, `production.batch_completed` on the final delta. |
| `art-backend:v33` | Retired | Sales report accepts optional `customer_id`; response gains `selected_customer` block and per-customer `order_items` list; CSV filename becomes `customer-report-<slug>-<YYYY-MM-DD>.csv` when filtered. |
| `art-backend:v34` | Retired | Sales report adds optional `order_id` (requires `customer_id`); response gains `selected_order` block; CSV filename becomes `customer-report-<slug>-order-<id>-<YYYY-MM-DD>.csv` when both filters are set. New error codes: `order_id_requires_customer_id` (422), `order_not_found` (404), `order_not_for_customer` (422). No DB migration. |
| `art-backend:v35` | **Live** | RBAC — five-role authorization matrix. Extends `UserRole` enum with `director`, `production_manager`, `warehouse_manager`. Migration `012_extend_user_roles` adds the new ENUM values via `ALTER TYPE userrole ADD VALUE IF NOT EXISTS …` (non-destructive, forward-only). Centralized `require_roles(*allowed)` factory + role-group constants in `app.dependencies`. Per-route guards rewritten across all routers. Service helpers `can_assign_role` / `can_manage_user` / `is_last_active_admin`. New error codes: `role_assignment_denied` (403), `user_management_denied` (403), `self_role_change_denied` (403), `self_deactivation_denied` (403), `last_admin_required` (422). Tests: `backend/tests/test_authorization_matrix.py` (51 passed, 2 skipped). |
| `art-frontend:v20` | Retired | Last working pre-gallery frontend. |
| `art-frontend:v21` | **Forbidden** | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed at runtime in Azure with PostCSS / Tailwind error. |
| `art-frontend:v22` | **Forbidden** | Production build, but MSYS-mangled `NEXT_PUBLIC_API_URL` poisoned every client-side fetch. |
| `art-frontend:v23` | **Forbidden** | Same MSYS poisoning as v22 plus the v23 modal defensive logic. |
| `art-frontend:v24` | Retired | Built with `MSYS_NO_PATHCONV=1`. Clean `/api/v1` base URL. Ships defensive modal logic from v23. |
| `art-frontend:v25`–`v27` | Retired | Orders list / detail UX: stock-aware status dropdown, friendlier shortage messaging (paired with backend v31). |
| `art-frontend:v28` | Retired | Production page: per-batch delta inputs (Լավ + Խոտան), running cumulative + remaining display, "Բոլոր մնացածը …" shortcuts (paired with backend v32). |
| `art-frontend:v29` | Retired | Reports page: per-customer sales report — customer dropdown, "Ընտրված հաճախորդ" header, "Order Items" table (paired with backend v33). |
| `art-frontend:v30` | Retired | Reports page bug fix — customer / material dropdowns now request `?limit=100` (the backend's declared cap) instead of `?limit=200` which was silently failing 422 and leaving both dropdowns empty. |
| `art-frontend:v31` | Retired | Reports page: per-order sales report — second dropdown ("Պատվեր") appears after a customer is selected and a customer-scoped report has been generated, populated from the response's `order_items`. Selecting an order re-generates the report scoped to that order; "Բոլոր պատվերները" returns to all-orders view. |
| `art-frontend:v32` | **Live** | RBAC — sidebar / dashboard route / user-form gating per role. New `frontend/src/lib/permissions.ts` (single source of truth: `MODULE_ACCESS`, `canAccessModule`, `canAssignRole`, `allowedRolesFor`, `ROLE_LABELS`). `requireRoles(...)` and `requireModule(module)` helpers added to `frontend/src/lib/auth.ts`. Sidebar / TopHeader / MobileNav driven by `canAccessModule` and `ROLE_LABELS`. Dashboard route guards migrated from binary admin/user to per-module / per-role checks. User-create and user-edit forms restrict the role `<Select>` options via `allowedRolesFor(actor)`; the role select is disabled on self-edit (UI hint matching the backend self-role-change guard). New Armenian labels: `Տնօրեն`, `Արտադրության ղեկավար`, `Պահեստապետ`. |

Blacklisted in `terraform/envs/dev/variables.tf` validation:
- Frontend: `v13`, `v21`, `v22`, `v23`.
- Backend: `v13`, `v26`, `v27`.

These tags cannot be redeployed accidentally — Terraform refuses to plan with them.

## Deployment workflow

Terraform is the source of truth. **Do not** make changes through the Azure Portal or `az` CLI — they will drift away from state and be overwritten on the next `terraform apply`.

### Standard apply

```bash
cd terraform/envs/dev
source .env.terraform                  # loads ARM_* env vars
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

`source .env.terraform` only affects the current shell — re-source in a new terminal. Do **not** use `az login` or any other Azure CLI command (see CLAUDE.md "Terraform Authentication Rule").

### Publishing a new image and rolling it out

1. **Build** locally. Frontend production build (run from Git Bash on Windows) **must** use `MSYS_NO_PATHCONV=1` to prevent path-arg mangling — see CLAUDE.md "Building Docker images on Windows / Git Bash":

   ```bash
   # Backend
   docker build -f backend/Dockerfile -t hoso30/art-backend:vN ./backend

   # Frontend (Git Bash on Windows)
   MSYS_NO_PATHCONV=1 docker build -f frontend/Dockerfile.azure -t hoso30/art-frontend:vN \
     --build-arg "INTERNAL_API_URL=https://app-art-backend-dev-art4242.azurewebsites.net" \
     --build-arg "NEXT_PUBLIC_API_URL=/api/v1" \
     --build-arg "NEXT_PUBLIC_APP_NAME=ART Manufacturing" \
     ./frontend
   ```

2. **Verify** the frontend image isn't poisoned before pushing:

   ```bash
   docker run --rm hoso30/art-frontend:vN sh -c \
     'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
   # Empty output required. Any match → do not push.
   ```

3. **Push:**

   ```bash
   docker push hoso30/art-backend:vN
   docker push hoso30/art-frontend:vN
   ```

4. **Bump the tag** in `terraform/envs/dev/terraform.tfvars` (and the default in `variables.tf` if you also want to change the default for other envs).

5. **Apply** as above. Expected plan shape: `1 to change, 0 to add, 0 to destroy` (or `2 to change` if you bump both tags). Anything else means an unrelated drift; investigate before applying.

### Verification after apply

```bash
terraform output | grep -E "deployed_image|backend_image|frontend_url|backend_url"

# Frontend (must serve the homepage HTML, no build errors)
curl -s -o /tmp/fe.html -w "HTTP %{http_code}\n" "$(terraform output -raw frontend_url)/"
grep -ci "Module parse failed\|Failed to compile" /tmp/fe.html  # must be 0

# Backend (must return JSON)
curl -i "$(terraform output -raw backend_url)/api/v1/products/public?limit=8" | head -5

# Verify the deployed frontend chunk has no MSYS-poisoned URL
CHUNK=$(curl -s "$(terraform output -raw frontend_url)/dashboard/production" \
  | grep -oE '/_next/static/chunks/app/dashboard/production/page-[a-f0-9]+\.js' | head -1)
curl -s "$(terraform output -raw frontend_url)$CHUNK" | grep -c "C:/Program Files/Git"
# Must be 0.
```

If Azure responds during apply with `HTTP response was nil; connection may have been reset`, retry once with `terraform apply -refresh=false`.

## Application settings (managed by Terraform)

App Service application settings on the backend Web App are set in `main.tf` and **must not** be edited manually in the portal. The azurerm provider performs a full sync of the `app_settings` map on every apply — any portal-added setting that isn't declared in `main.tf` is removed on the next `terraform apply`. Terraform is the source of truth.

### Backend Web App

| Setting | Value | Source |
|---|---|---|
| `WEBSITES_PORT` | `8000` | `var.backend_port` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `false` | hardcoded (Azure platform) |
| `APP_ENV` | `production` | hardcoded |
| `DEBUG` | `false` | hardcoded |
| `LOG_FORMAT` | `json` | hardcoded |
| `SECRET_KEY` | from gitignored `terraform.tfvars` | `var.backend_secret_key` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | hardcoded |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | hardcoded |
| `ALLOWED_ORIGINS` | computed | `https://${module.naming.web_app_frontend}.azurewebsites.net` |
| `DATABASE_URL` (asyncpg) | computed | `art_app` user + `random_password.art_app_db.result` + Postgres FQDN + `?ssl=require`. Runtime DB user is the **least-privilege `art_app` role** (Task C1) — SELECT/INSERT/UPDATE/DELETE only, no DDL. |
| `DATABASE_URL_SYNC` (psycopg2) | computed | `var.postgres_admin_user` (`art_admin`) + `random_password.postgres_admin.result` + Postgres FQDN + `?sslmode=require`. Used by Alembic migrations and by `scripts/bootstrap_db_user.py` only. |
| `ART_APP_DB_PASSWORD` | computed | `random_password.art_app_db.result`. Read by `scripts/bootstrap_db_user.py` to set/rotate the `art_app` role's password on each cold start. |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | `redis://127.0.0.1:6379/0` and `/1` | `var.redis_port`. Shared loopback inside the backend Web App (sidecars). |
| `STORAGE_BACKEND` | `azure` | `var.backend_storage_backend`. `minio` is local-dev only — never set to `minio` in Azure. |
| `AZURE_STORAGE_ACCOUNT_URL` | computed | `azurerm_storage_account.images.primary_blob_endpoint`. The backend's adapter constructs `BlobServiceClient(account_url, DefaultAzureCredential())` and authenticates via the Web App's System-Assigned identity (Task C2a/C2b). |
| `AZURE_STORAGE_CONTAINER` | `art-images` | `azurerm_storage_container.images.name` |
| `AZURE_STORAGE_CONNECTION_STRING` | **REMOVED in C2b.** | The setting is no longer in `app_settings`. The storage account also has `shared_access_key_enabled = false`, so even if the setting were resurrected, the data plane would refuse shared-key auth. |

### Frontend Web App

| Setting | Value | Source |
|---|---|---|
| `WEBSITES_PORT` | `3000` | `var.container_port` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `false` | hardcoded |
| `NODE_ENV` | `production` | hardcoded |
| `INTERNAL_API_URL` | computed | `https://${module.naming.web_app_backend}.azurewebsites.net`. **Inert at runtime** — Next.js standalone bakes the rewrite destination at frontend image build time via the matching `--build-arg`. The App Setting is declared so the value is visible in the portal and ready if a future SSR runtime read is added. Bumping it without a fresh frontend image build has no effect. |
| `NEXT_PUBLIC_API_URL` | `/api/v1` | hardcoded — must stay relative so SameSite=Lax cookies ride client-side fetches. |

### Why ALLOWED_ORIGINS / INTERNAL_API_URL use `module.naming.*` instead of resource attributes

Both directions can't reference `azurerm_linux_web_app.X.default_hostname` or Terraform errors with a graph cycle (backend depends on frontend, frontend depends on backend). The naming module is a pure-string output `app-${project}-${component}-${environment}-${suffix}` driven by the same variables that name the Web Apps themselves, so the values are guaranteed identical to the actual hostnames as long as no custom domain is bound. Both settings remain 100% Terraform-managed — no portal edit can persist.

### Storage authentication after C2b — Managed Identity only

```
Backend Web App (System-Assigned identity)
  └── principal_id = 8b108e0c-10af-4d3d-9a34-5f372f684064
       └── role: Storage Blob Data Contributor
            scope: storageAccounts/startdevimgsart4242
```

- `azurerm_role_assignment.backend_blob_data_contributor[0]` — created in Task C2a stage 2.
- `azurerm_storage_account.images.shared_access_key_enabled = false` — set in Task C2b. Blocks shared-key auth at the data plane regardless of whether keys leak.
- The `azurerm` provider has `storage_use_azuread = true` (in `providers.tf`) so `terraform plan` can read storage data-plane sub-properties (`queue_properties`, etc.) via the SP's Entra ID token instead of shared keys. **The SP must therefore hold `Storage Blob Data Reader` (or higher) on the storage account scope** for plans to work — currently inherited from subscription-scope Owner. If the SP is downgraded back to Resource Manager `Contributor`, grant explicit `Storage Blob Data Owner` on `azurerm_storage_account.images` or plans will 403 on `KeyBasedAuthenticationNotPermitted`.

### PostgreSQL authentication — split-role

- **Application runtime** uses `art_app` (least-privilege role created on each cold start by `backend/scripts/bootstrap_db_user.py`). Granted `CONNECT` on the database, `USAGE` on schema `public`, and `SELECT/INSERT/UPDATE/DELETE` on tables + sequences. **No DDL, no role management, no superuser.**
- **Migrations and bootstrap** use `art_admin` (server administrator from `var.postgres_admin_user` + `random_password.postgres_admin`). `DATABASE_URL_SYNC` carries this DSN; `entrypoint.sh` runs Alembic against it, then `scripts/bootstrap_db_user.py` against it (which idempotently creates `art_app`, sets its password from `ART_APP_DB_PASSWORD`, and re-grants the privileges), and only then does `uvicorn` start using `DATABASE_URL` (the `art_app` DSN).
- A leaked runtime DSN therefore cannot drop tables, exfiltrate via `COPY ... TO PROGRAM`, or escalate privileges.

## Sensitive files (never commit, never echo)

These three files contain secrets that the deployment depends on. Every contributor must respect this list:

| File | Why sensitive | Status |
|---|---|---|
| `terraform/envs/dev/.env.terraform` | Contains the four `ARM_*` Service Principal credentials. Anyone with these can fully control the Azure subscription. | **Gitignored.** Never `cat`, never paste into chat / commits / commit messages. |
| `terraform/envs/dev/terraform.tfvars` | Contains `backend_secret_key` (JWT signing key) and persists `enable_storage_role_assignment = true`. JWT key compromise = mint admin tokens. | **Gitignored.** |
| `terraform/envs/dev/terraform.tfstate` | Contains generated Postgres admin password, `art_app` DB password, storage account access keys (used to compute `primary_connection_string` in state output even though shared-key auth is disabled at the data plane). | **Gitignored.** Treat as an offline secret store; if shared with a teammate, share over a secure channel. Future hardening: move to remote backend (Azure Storage with blob lease lock) so state is encrypted at rest with audit trail. |

The `storage_account_connection_string` Terraform output is marked `sensitive` and will not print without `terraform output -raw`. Even with `shared_access_key_enabled = false`, treat the connection string as confidential — it embeds the still-existing storage account access key. **Future hardening:** remove the `storage_account_connection_string` output from `outputs.tf` entirely once nothing in the workflow needs it.

## Critical Data Protection (PostgreSQL & Azure Blob Storage)

The PostgreSQL Flexible Server and the Azure Storage Account hold every order, customer, product, audit-log row, and uploaded product image. They are protected by **two independent layers** and both must remain in place by default.

**Layer 1 — Terraform `prevent_destroy = true`** is set in lifecycle blocks on:

- `azurerm_postgresql_flexible_server.this`
- `azurerm_postgresql_flexible_server_database.app`
- `azurerm_storage_account.images`
- `azurerm_storage_container.images`

Any `terraform plan` containing a destroy or replace for these fails before apply.

**Layer 2 — Azure resource locks** (`CanNotDelete`, free under Resource Manager) declared in `main.tf` as:

- `azurerm_management_lock.postgres_no_delete` → scope: Postgres server (covers the database)
- `azurerm_management_lock.storage_no_delete` → scope: Storage Account (covers the container and all blobs)

Locks block DELETE via portal, `az` CLI, ARM API, and Terraform itself. They allow reads and updates, so:

- bumping `frontend_image_tag` / `backend_image_tag` ✓
- changing an `app_settings` value ✓
- creating or updating containers / blobs / firewall rules ✓
- rotating the Postgres admin password ✓
- rotating Storage Account access keys ✓

…all continue to work. Only DELETE is blocked.

### Pre-apply checklist (mandatory before every `terraform apply`)

Scan the plan output for any of these strings — **any match means stop and surface to the user**:

- `-/+ azurerm_postgresql_flexible_server.this`
- `-/+ azurerm_postgresql_flexible_server_database.app`
- `-/+ azurerm_storage_account.images`
- `-/+ azurerm_storage_container.images`
- `-/+ azurerm_management_lock.postgres_no_delete`
- `-/+ azurerm_management_lock.storage_no_delete`
- any `- destroy` against the names above

The expected shape for normal changes (image bump, app-setting tweak) is `N to change, 0 to add, 0 to destroy` against the Web App resources only.

### Removing the protections (only foreseen scenario: West Europe migration)

When the `LocationIsOfferRestricted` subscription block lifts and PostgreSQL is migrated from North Europe to West Europe, the recreate is genuinely required. The procedure (each step is its own user approval):

1. `pg_dump` of `art_manufacturing` to a local file. Verify the dump opens cleanly in `pg_restore --list`.
2. Comment out `azurerm_management_lock.postgres_no_delete` in `main.tf`. `terraform apply` → lock removed.
3. Comment out `prevent_destroy = true` on both Postgres lifecycle blocks (server + database). `terraform apply` with the new `postgres_location = "West Europe"` → server recreated.
4. `pg_restore` from the dump.
5. Restore both lifecycle lines and the lock resource. `terraform apply` → re-protected.

Same procedure with Storage analogues if the Storage Account ever needs to be recreated (replace `pg_dump`/`pg_restore` with `azcopy` blob-to-blob copy).

## Cost guardrails ($0 target while the 12-month free tier runs)

- **App Service Plans must remain F1 Free.** Both `asp-art-dev` and `asp-art-backend-dev`.
- **PostgreSQL Flexible Server must remain `B_Standard_B1ms`** with 32 GB storage, 7-day backup retention, no HA, no geo-redundant backups. The free 12-month allowance covers exactly one B1MS server per subscription. Validation in `variables.tf` and a `lifecycle.precondition` block both enforce this.
- **Storage Account must remain `Standard_LRS`, StorageV2, Hot tier.** Free 12-month allowance: 5 GB storage, 20 000 reads, 10 000 writes per month. Public-blob access is disabled at account level; the `art-images` container is private. Watch `Cost analysis` for any deviation.
- **No paid resource added without explicit approval and a Cost Impact block** (see CLAUDE.md §6).
- **Set a $1/month subscription budget** with email alerts. Anything above $0 during the 12-month window is a regression.

After the 12-month window expires, B1MS bills ~$15/month and 32 GB SSD bills ~$3.70/month — see `terraform/envs/dev/README.md` "Cost after the 12-month free tier expires" section for the migration plan.

## Verifying confirmed-working features

Each feature below is part of the live deployment as of v32 (frontend) / v35 (backend):

| Feature | Manual check |
|---|---|
| Homepage renders | `curl -i "$(terraform output -raw frontend_url)/"` → HTTP 200, ≥30 KB HTML, no build-error markers |
| Login + dashboard | Browser: log in as `admin@art-manufacturing.com / admin123456`, hit `/dashboard` |
| Public product list | `curl -i "$(terraform output -raw backend_url)/api/v1/products/public?limit=8"` → HTTP 200, JSON `{items:[...], total, page, limit}` |
| Product image gallery | Open `/catalog/<id>`. Click a thumbnail to open the lightbox. ←/→/Esc work |
| Production modal product dropdown | `/dashboard/production` → "Ստեղծել արտադրություն" → "Ապրանք *" populates with all products |
| Image upload to Azure Blob | Admin: `/dashboard/products/<id>` → upload a JPG/PNG/WebP → see it appear in the gallery; HEAD request to `/api/v1/products/images/file/<key>` returns `image/*` |
| Audit log | `/dashboard/activity` shows recent mutations with Armenian action labels |
| Sales report — all customers | `/dashboard/reports` → "Վաճառքների հաշվետվություն" → leave customer empty → "Ստեղծել Հաշվետվություն" → summary cards reflect every revenue-eligible order. CSV downloads as `sales_report.csv`. |
| Sales report — one customer | Same page, pick a customer, generate. Header shows "Ընտրված հաճախորդ"; summary, by-day, by-customer, and Order Items table all scope to that customer. CSV downloads as `customer-report-<slug>-<YYYY-MM-DD>.csv`. |
| Sales report — one customer + one order | After generating a customer-scoped report, the "Պատվեր" dropdown appears, populated from the response's `order_items`. Pick an order, regenerate. Header shows "Ընտրված պատվեր: #N"; every section scopes to that single order. CSV downloads as `customer-report-<slug>-order-<id>-<YYYY-MM-DD>.csv`. |
| RBAC — five user roles | Browser: log in as admin → sidebar shows full nav. Backend: `curl -i $(terraform output -raw backend_url)/api/v1/users -b cookies.txt` returns 200 with all users. Pydantic rejects unknown role: `curl … -X POST … -d '{"email":"x@y.com","password":"Passw0rd!","role":"hacker"}'` returns 422. Director restriction: a director's `GET /users` lists only `simple_user` rows; `POST /users` with `role:"admin"` returns 403 `role_assignment_denied`. Self-role-change: admin's `PATCH /users/{own_id}` with `{"role":"simple_user"}` returns 403 `self_role_change_denied`. New Armenian labels visible in the user create/edit modals' role `<Select>`: `Տնօրեն` / `Արտադրության ղեկավար` / `Պահեստապետ`. |

### Sales report API — error contract

`GET /api/v1/reports/sales` accepts these query combinations:

| Query | Status | Notes |
|---|---|---|
| (no filters) | 200 | All revenue-eligible orders. `selected_customer = null`, `selected_order = null`, `order_items = []`. |
| `customer_id=N` | 200 | Scoped to customer N. `selected_customer` populated, `order_items` populated. 404 `customer_not_found` if N doesn't exist. |
| `customer_id=N&order_id=M` | 200 | Scoped to order M (must belong to customer N). `selected_order` populated. |
| `order_id=M` (no `customer_id`) | **422** `order_id_requires_customer_id` | Order filter is only meaningful in the per-customer flow. |
| `customer_id=N&order_id=M` (M missing) | **404** `order_not_found` | |
| `customer_id=N&order_id=M` (M belongs to L≠N) | **422** `order_not_for_customer` | Ownership mismatch. |

## Known limitations (current state, not bugs)

1. **F1 cold starts** add 30–60 s after ~20 min idle. `always_on` is unavailable on F1; mitigate at the app layer (warm-up ping) or accept it for dev usage.
2. **F1 daily CPU budget** is 60 min/day across each plan. A runaway worker task can exhaust it; check `/Cost+Quotas` if requests start returning 403.
3. **PostgreSQL is in North Europe** while everything else is in West Europe. Caused by `LocationIsOfferRestricted`; cross-region egress stays inside the 100 GB/month always-free allowance for any realistic dev workload. To consolidate when the restriction is lifted, set `postgres_location = "West Europe"` and re-apply (recreates the server — `pg_dump` first).
4. **B1MS connection cap (~50)** vs. SQLAlchemy `pool_size=20, max_overflow=10` × uvicorn `--workers 2` → worst-case 60 connections. Mitigations in `terraform/envs/dev/README.md`.
5. **Backend `/health` endpoint** runs alembic on first cold start, so the very first request after a deploy can take 20–45 s.

## Where to look when something breaks

- **Frontend Web App logs:** Portal → `app-art-frontend-dev-art4242` → Monitoring → Log stream. Or Kudu: `https://app-art-frontend-dev-art4242.scm.azurewebsites.net`.
- **Backend Web App logs (all containers):** Portal → `app-art-backend-dev-art4242` → Monitoring → Log stream. Per-sidecar logs: Deployment Center → Containers → click container row → Logs.
- **PostgreSQL queries:** `psql "host=$(terraform output -raw postgres_fqdn) port=5432 user=$(terraform output -raw postgres_admin_user) dbname=$(terraform output -raw postgres_database) sslmode=require"` with `PGPASSWORD="$(terraform output -raw postgres_admin_password)"`.
- **Storage Account contents:** Portal → `startdevimgsart4242` → Containers → `art-images`. Or `az storage blob list -c art-images --account-name startdevimgsart4242` (this is one of the few `az` commands acceptable for read-only diagnostics; Terraform auth still uses the SP).
- **Image-tag drift:** `terraform output | grep image`. If the deployed value doesn't match what's in `terraform.tfvars`, somebody applied without committing — investigate before re-applying.

## Related docs

- `terraform/envs/dev/README.md` — variable reference, free-tier rules, expected plans, destroy procedure.
- `handoff/CURRENT_STATE.md` — branch / migration / test status snapshot.
- `handoff/KNOWN_RISKS.md` — incident-driven failure modes and rules.
- `handoff/SAFE_TASK_RULES.md` — operational guardrails.
- `CLAUDE.md` — Terraform auth rule, Windows-build rule, free-tier allowlist, Armenian text rules.
