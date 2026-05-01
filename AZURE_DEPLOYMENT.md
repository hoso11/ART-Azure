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
- **No MinIO sidecar.** Replaced by Azure Blob Storage in Phase 4. The MinIO sitecontainer resource is still in `main.tf` but defaults to `minio_sidecar_enabled = false`. MinIO remains the local-dev backend in `docker-compose.yml`.
- **No Application Insights / Log Analytics.** Logs available via portal Log Stream and Kudu only.
- **No Key Vault.** PostgreSQL admin password lives in `terraform.tfstate` (gitignored).
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
| `art-backend:v21` | **Live** | Backend-agnostic image proxy (works with both MinIO and Azure Blob). Phase 5 image gallery support. |
| `art-frontend:v20` | Retired | Last working pre-gallery frontend. |
| `art-frontend:v21` | **Forbidden** | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed at runtime in Azure with PostCSS / Tailwind error. |
| `art-frontend:v22` | **Forbidden** | Production build, but MSYS-mangled `NEXT_PUBLIC_API_URL` poisoned every client-side fetch. |
| `art-frontend:v23` | **Forbidden** | Same MSYS poisoning as v22 plus the v23 modal defensive logic. |
| `art-frontend:v24` | **Live** | Built with `MSYS_NO_PATHCONV=1`. Clean `/api/v1` base URL. Ships defensive modal logic from v23. |

`v13`, `v21`, `v22`, `v23` are blocked by the `frontend_image_tag` validation in `terraform/envs/dev/variables.tf` so they cannot be redeployed accidentally.

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

# Verify the deployed v24 chunk has no MSYS-poisoned URL
CHUNK=$(curl -s "$(terraform output -raw frontend_url)/dashboard/production" \
  | grep -oE '/_next/static/chunks/app/dashboard/production/page-[a-f0-9]+\.js' | head -1)
curl -s "$(terraform output -raw frontend_url)$CHUNK" | grep -c "C:/Program Files/Git"
# Must be 0.
```

If Azure responds during apply with `HTTP response was nil; connection may have been reset`, retry once with `terraform apply -refresh=false`.

## Application settings (managed by Terraform)

App Service application settings on the backend Web App are set in `main.tf` and **must not** be edited manually in the portal. The relevant ones:

| Setting | Value | Source |
|---|---|---|
| `WEBSITES_PORT` | `8000` (backend) / `3000` (frontend) | hardcoded |
| `APP_ENV` | `production` | hardcoded |
| `LOG_FORMAT` | `json` | hardcoded |
| `SECRET_KEY` | tfvars / generated | `var.backend_secret_key` |
| `DATABASE_URL` (asyncpg) | computed | Postgres FQDN + admin password + `?ssl=require` |
| `DATABASE_URL_SYNC` (psycopg2) | computed | Postgres FQDN + admin password + `?sslmode=require` |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | `redis://localhost:6379/…` | shared network namespace inside backend Web App |
| `STORAGE_BACKEND` | `azure` | tfvars (was `minio` pre-Phase-4) |
| `AZURE_STORAGE_CONNECTION_STRING` | computed | from `azurerm_storage_account.this.primary_connection_string`, sensitive |
| `AZURE_BLOB_CONTAINER` | `art-images` | tfvars |
| `INTERNAL_API_URL` | backend Web App URL | only consumed by frontend image at **build time** — App Setting present for completeness |
| `ALLOWED_ORIGINS` | frontend URL | for CORS / cookie handling |

The frontend Web App also has an `INTERNAL_API_URL` setting, but that value is **inert** because Next.js standalone bakes the rewrite destination at build time. The build-arg above is what actually wires the routing.

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

Each feature below is part of the live deployment as of v24 (frontend) / v21 (backend):

| Feature | Manual check |
|---|---|
| Homepage renders | `curl -i "$(terraform output -raw frontend_url)/"` → HTTP 200, ≥30 KB HTML, no build-error markers |
| Login + dashboard | Browser: log in as `admin@art-manufacturing.com / admin123456`, hit `/dashboard` |
| Public product list | `curl -i "$(terraform output -raw backend_url)/api/v1/products/public?limit=8"` → HTTP 200, JSON `{items:[...], total, page, limit}` |
| Product image gallery | Open `/catalog/<id>`. Click a thumbnail to open the lightbox. ←/→/Esc work |
| Production modal product dropdown | `/dashboard/production` → "Ստեղծել արտադրություն" → "Ապրանք *" populates with all products |
| Image upload to Azure Blob | Admin: `/dashboard/products/<id>` → upload a JPG/PNG/WebP → see it appear in the gallery; HEAD request to `/api/v1/products/images/file/<key>` returns `image/*` |
| Audit log | `/dashboard/activity` shows recent mutations with Armenian action labels |

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
