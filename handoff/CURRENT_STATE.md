# Current State

Snapshot as of the most recent verified working tree on `v12`. Future agents: confirm each line by running the listed verification command before relying on it — this file ages.

## Azure deployment — currently live

| Component | State | Live value |
|---|---|---|
| Resource group | applied | `rg-art-dev` (West Europe) |
| Frontend Web App | applied, serving | `app-art-frontend-dev-art4242` on `asp-art-dev` (F1 Free) — image `hoso30/art-frontend:v32` |
| Backend Web App | applied, serving | `app-art-backend-dev-art4242` on `asp-art-backend-dev` (F1 Free) — image `hoso30/art-backend:v35`. **System-Assigned identity** (Task C2a) — principal_id `8b108e0c-10af-4d3d-9a34-5f372f684064`. |
| Backend `worker` sidecar | applied | image `hoso30/art-backend:v35`, running Celery worker + beat |
| Backend `redis` sidecar | applied | `redis:7-alpine`, internal-only |
| Backend `minio` sidecar | disabled | `minio_sidecar_enabled = false` since Phase 4. Sitecontainer resource still exists in `main.tf` for parity. **Never enable in Azure** — MinIO is local-dev-only. |
| PostgreSQL Flexible Server | applied, serving | `psql-art-dev-art4242` (B_Standard_B1ms, PG 16, 32 GB, 7-day backup, **North Europe** — see PostgreSQL exception in CLAUDE.md). **Two roles in use** (Task C1): `art_admin` for Alembic + bootstrap, `art_app` (least-privilege CRUD only) for application runtime. |
| Storage Account | applied | `startdevimgsart4242` (Standard_LRS, StorageV2, Hot). **`shared_access_key_enabled = false`** (Task C2b) — only Entra ID/Managed Identity tokens accepted at the data plane. |
| Blob container | applied | `art-images` (private) — browsers fetch via backend `/api/v1/products/images/file/{key}` proxy. Backend authenticates via Managed Identity. |
| Storage role assignment | applied | `azurerm_role_assignment.backend_blob_data_contributor[0]` — `Storage Blob Data Contributor` on the storage account scope, principal_id = backend Web App's MI. Gated by `var.enable_storage_role_assignment = true` in tfvars (Task C2a two-stage apply pattern). |
| Cost target | preserved | $0/month while the 12-month free tier is active |
| Data protection | enforced | All four data resources (`azurerm_postgresql_flexible_server.this`, `…_database.app`, `azurerm_storage_account.images`, `azurerm_storage_container.images`) carry `lifecycle { prevent_destroy = true }`. Two `azurerm_management_lock` resources (`postgres_no_delete`, `storage_no_delete`) hold `CanNotDelete` Azure-side locks scoped to the server and the storage account; locks inherit to the database and the container. See `handoff/KNOWN_RISKS.md` #10 and `handoff/SAFE_TASK_RULES.md` "Critical Data Protection". |
| Terraform provider config | `storage_use_azuread = true` | Required since Task C2b (`shared_access_key_enabled = false`) so the provider can read storage account data-plane sub-properties (`queue_properties` etc.) via Entra ID instead of shared keys. The SP must therefore hold a Storage data-plane RBAC role (`Storage Blob Data Reader` or higher) on the storage account or `terraform plan` 403s with `KeyBasedAuthenticationNotPermitted`. |
| Terraform SP role | **Owner** at subscription scope | The SP currently holds **Owner** (elevated for Task C2a role-assignment creation, retained for ongoing Storage data-plane reads required by the provider after C2b). Day-to-day operations (image bumps, app settings, password rotations, firewall rules) only need Contributor + a Storage data-plane role; if the SP is downgraded to Contributor, grant explicit `Storage Blob Data Owner` on `azurerm_storage_account.images` to keep `terraform plan` working. **Re-grant Owner only when adding/modifying lock resources or role assignments** — see `handoff/SAFE_TASK_RULES.md` "Service Principal role for Terraform". |

Verify image tags after any apply:

```bash
cd terraform/envs/dev
source .env.terraform
terraform output | grep -E "deployed_image|backend_image"
# deployed_image = "hoso30/art-frontend:v32"
# backend_image  = "hoso30/art-backend:v35"
```

Verify the live security stack:

```bash
# Storage shared keys disabled at the data plane:
terraform state show azurerm_storage_account.images | grep shared_access_key_enabled
#   shared_access_key_enabled = false

# Connection string removed from backend app_settings:
terraform state show azurerm_linux_web_app.backend | grep AZURE_STORAGE
#   "AZURE_STORAGE_ACCOUNT_URL" = "https://startdevimgsart4242.blob.core.windows.net/"
#   "AZURE_STORAGE_CONTAINER"   = "art-images"
# (no AZURE_STORAGE_CONNECTION_STRING line)

# Role assignment retained:
terraform state show 'azurerm_role_assignment.backend_blob_data_contributor[0]' | grep -E "principal_id|role_definition_name|scope"
```

Full topology and verification commands: see `AZURE_DEPLOYMENT.md`. Variable reference and free-tier rules: see `terraform/envs/dev/README.md`.

## Sensitive files — never commit

| File | Sensitive content |
|---|---|
| `terraform/envs/dev/.env.terraform` | Service Principal credentials (`ARM_*`). Subscription-level access. |
| `terraform/envs/dev/terraform.tfvars` | `backend_secret_key` (JWT signing key) and `enable_storage_role_assignment = true`. |
| `terraform/envs/dev/terraform.tfstate` (+ `.backup`) | Postgres admin password, `art_app` runtime password, storage account access keys (used to compute the `storage_account_connection_string` output even though shared-key auth is disabled). |

All three are gitignored. Never echo their contents into chat/commits/logs. The `storage_account_connection_string` Terraform output is marked sensitive — treat it as confidential even though `shared_access_key_enabled = false` makes the embedded key inert at the data plane. **Future hardening:** remove that output entirely.

## Branch and commit

- Active branch: `v12` (1 commit ahead of `origin/v12`, not pushed, not merged).
- Most recent committed work: `ef49b8d` — "Production rewrite, order/product UX fixes, and homepage cleanup".
- Uncommitted in working tree: Phase 1 Խոտան (partial-outcome) feature + damaged-stock report. Not yet committed at the time this snapshot was written.
- Verify: `git log --oneline -5` and `git status --short`.

## Alembic head

- Current head: **`012_extend_user_roles`** (down-revision `011_order_stock_deducted`).
- Migration files on disk (`backend/alembic/versions/`):
  - `001_initial`
  - `002_var_mat_req`
  - `003_user_discount`
  - `004_order_materials_deducted`
  - `006_order_item_fulfillment`  *(no 005 file — intentional, it was removed during an earlier rollback)*
  - `007_production_batches`
  - `008_activity_log_columns`
  - `010_batch_partial_outcome`  *(no 009 file — see `KNOWN_RISKS.md` #1)*
  - `011_order_stock_deducted`
  - `012_extend_user_roles`
- **No `009_*` migration exists. It must not be reintroduced — see `KNOWN_RISKS.md` #1.**
- Verify: `ls backend/alembic/versions/` and `docker-compose exec backend alembic current`.

### Migration 012 details — RBAC enum extension

`012_extend_user_roles.py` extends the existing `userrole` Postgres ENUM with three new values via three idempotent statements. Non-destructive — existing rows are untouched, and `IF NOT EXISTS` makes re-runs safe:

```sql
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'director';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'production_manager';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'warehouse_manager';
```

`downgrade()` is a documented no-op: Postgres ENUMs do not support `ALTER TYPE … DROP VALUE`. Removing a value would require dropping the column, dropping the type, recreating both with the original two values, and restoring data — a destructive operation that is not part of the rollback path. **Migration is forward-only.** This shapes the rollback caveat — see `ROLLBACK_NOTES.md` "RBAC ENUM extension is forward-only".

### Migration 010 details

`010_batch_partial_outcome.py` adds INT/TEXT-only columns — no enum, no CAST, no varchar(32) revision-id risk:

- `production_batches.good_quantity INT NOT NULL DEFAULT 0`
- `production_batches.damaged_quantity INT NOT NULL DEFAULT 0`
- `production_batches.defect_reason TEXT NULL`
- `product_variants.damaged_stock_quantity INT NOT NULL DEFAULT 0`

Server defaults fill existing rows, so no backfill is needed. **Verified end-to-end on a clean Postgres DB** (created `art_migration_test`, ran `alembic upgrade head` → `010_batch_partial_outcome (head)`, verified columns and server-default behavior, verified downgrade reverses cleanly, dropped temp DB). Main `art_manufacturing` DB was not touched during verification.

## Entrypoint guard (`backend/entrypoint.sh`)

The boot script reads `alembic_version.version_num` and rewrites it to `006_order_item_fulfillment` if the value is not in this whitelist:

```
{None, 001_initial, 002_var_mat_req, 003_user_discount,
 004_order_materials_deducted, 006_order_item_fulfillment,
 007_production_batches, 008_activity_log_columns,
 010_batch_partial_outcome, 011_order_stock_deducted,
 012_extend_user_roles}
```

Designed to recover databases stamped at a now-deleted revision (e.g. `005_production_records` or a transient `009_*`). The rewrite is silent — see `KNOWN_RISKS.md` for the caveat.

## Docker images

- Local code is the source of truth. Local tests are green (79 passing — `make test`).
- The publicly cached image `hoso30/art-backend:v13` contained the failed migration 009 rewrite and is **not safe to redeploy**. The current local code does *not* match `:v13`.
- Before publishing a new tag, build fresh from the current commit; do not pull `:v13` cache layers.

## Implemented features

| Feature | State | Key files |
|---|---|---|
| JWT auth (httpOnly cookies, refresh rotation) | done | `backend/app/auth/`, `frontend/src/lib/auth.ts` |
| Customer / Product / Order CRUD | done | `backend/app/{customers,products,orders}/` |
| Order item fulfillment split (`fulfilled_from_stock` / `production_quantity`) | done, migration `006` | `backend/app/orders/service.py` |
| Stock-based production batches | done, migration `007` | `backend/app/production/` (batch flow) |
| Audit log (~25 mutation events, admin page `/dashboard/activity`) | done, migration `008` | `backend/app/activity/`, `frontend/src/app/dashboard/activity/page.tsx` |
| Reports (7 endpoints + ReportBuilder UI) | done | `backend/app/reports/`, `frontend/src/app/dashboard/reports/` |
| Storage abstraction (MinIO local, Azure Blob deployed) | done | `backend/app/storage/` — `interface.py`, `minio_adapter.py`, `azure_adapter.py`. Adapter selects auth path: `BlobServiceClient(account_url, DefaultAzureCredential())` when `AZURE_STORAGE_ACCOUNT_URL` is set (Task C2a), else falls back to connection string (local dev). `STORAGE_BACKEND=minio` for compose, `azure` for deployed envs. |
| Multi-image product gallery (Phase 5) | done | `frontend/src/components/products/ProductCardImage.tsx`, `ProductImageGallery.tsx`. Clickable card → fullscreen lightbox with prev/next/thumbnails/Esc/←/→ keyboard nav. Backed by existing `ProductImage` schema (no migration). |
| Backend image proxy (backend-agnostic) | done | `backend/app/products/router.py::stream_image_file` reads via `storage.download_file()` so the same code path works against MinIO and Azure Blob. v21 fix; v20 was MinIO-only. |
| **Task A — Critical credentials hardening** | done, deployed v25+ | `WEAK_SECRET_KEYS` validator in `backend/app/config.py`; FastAPI docs gated in production via `_docs_kwargs` in `backend/app/main.py`; seed credentials gated by `ENABLE_SEED_DATA` + non-default `ADMIN_INITIAL_PASSWORD` in `backend/scripts/seed.py`. Tests in `backend/tests/test_security_hardening.py`. |
| **Task B — Auth surface hardening** | done, deployed v28+ | slowapi 5/min on login + 20/min on refresh with XFF-aware port-stripping `_client_ip` (`backend/app/rate_limit.py`); `OriginCheckMiddleware` in `backend/app/origin_check.py` blocks unsafe methods with bad/missing Origin/Referer; backend container runs as non-root `app:1001` (`backend/Dockerfile.azure`). Tests in `backend/tests/test_auth_surface_hardening.py`. |
| **Task C1 — PostgreSQL least-privilege runtime user** | done, deployed v29+ | `backend/scripts/bootstrap_db_user.py` runs from `entrypoint.sh` between Alembic and uvicorn; idempotently `CREATE ROLE art_app` (if missing), `ALTER ROLE art_app WITH PASSWORD <ART_APP_DB_PASSWORD>`, `GRANT CONNECT/USAGE/SELECT/INSERT/UPDATE/DELETE` + `ALTER DEFAULT PRIVILEGES`. Runtime `DATABASE_URL` connects as `art_app` (CRUD only, no DDL). `DATABASE_URL_SYNC` keeps the admin (`art_admin`) for Alembic + bootstrap. Tests in `backend/tests/test_db_bootstrap.py`. Terraform: `random_password.art_app_db` resource, `ART_APP_DB_PASSWORD` app setting, `postgres_app_password` output. |
| **Task C2a — Storage Managed Identity** | done, deployed v30 | Backend Web App has `identity { type = "SystemAssigned" }`, granted `Storage Blob Data Contributor` on the storage account scope (`azurerm_role_assignment.backend_blob_data_contributor[0]`). Backend adapter (`backend/app/storage/azure_adapter.py`) constructs `BlobServiceClient(account_url, DefaultAzureCredential())` when `AZURE_STORAGE_ACCOUNT_URL` is set. New dependency: `azure-identity==1.19.0`. Tests in `backend/tests/test_storage_managed_identity.py`. Two-stage apply gate: `var.enable_storage_role_assignment` (false default for the bootstrap workaround, true in tfvars after stage 2). |
| **Task C2b — Storage shared-key denial** | done | `AZURE_STORAGE_CONNECTION_STRING` removed from backend `app_settings`; `azurerm_storage_account.images.shared_access_key_enabled = false`. Provider configured with `storage_use_azuread = true` so plans can read storage data-plane sub-properties via Entra ID. SP must hold Storage Blob Data role on the storage account (currently inherited from subscription Owner). |
| Production page: one row per order (Option B, API aggregation, no migration) | done in `ef49b8d` | `GET /production?one_per_order=true`, `PATCH /production/orders/{id}/current`, `OrderCurrentControl.tsx` |
| Order detail items: product name + size/color | done in `ef49b8d` | `OrderItemResponse.product_variant`, `frontend/src/app/dashboard/orders/[id]/page.tsx` |
| Product image gallery (thumbnails + lightbox) | done in `ef49b8d` | `frontend/src/components/products/ProductImageGallery.tsx` |
| Homepage hardcoded translations removed | done in `ef49b8d` | `frontend/src/components/home/FeaturedProducts.tsx` |
| **Stock-based production: partial outcome (Խոտան)** | **done in working tree, migration `010`** | `backend/app/production/{models,schemas,service,router}.py`, `backend/app/products/{models,schemas}.py`, `BatchControl.tsx`, `frontend/src/app/dashboard/production/page.tsx`, `VariantActions.tsx`, `frontend/src/app/dashboard/products/[id]/page.tsx` |
| **Damaged-stock report (Խոտանի հաշվետվություն)** | **done in working tree** | `backend/app/reports/{service,router}.py`, `frontend/src/app/dashboard/reports/ReportBuilder.tsx`, `backend/tests/test_reports_damaged_stock.py` |
| **Sales report — per-customer + per-order export** | done, deployed v34 / v31 | `backend/app/reports/{service,router}.py`, `frontend/src/app/dashboard/reports/ReportBuilder.tsx`, `backend/tests/test_reports_sales.py`. `/reports/sales` accepts optional `customer_id` and (only when `customer_id` is set) optional `order_id`. Response carries `selected_customer` and `selected_order` blocks plus a per-line `order_items` list. CSV filename is `sales_report.csv` (unfiltered), `customer-report-<slug>-<YYYY-MM-DD>.csv` (customer-only), or `customer-report-<slug>-order-<id>-<YYYY-MM-DD>.csv` (customer + order). Error codes: `customer_not_found` (404), `order_id_requires_customer_id` (422), `order_not_found` (404), `order_not_for_customer` (422). No DB migration. Frontend: customer dropdown for orders/sales reports; order dropdown appears for sales after a customer is selected and a customer-scoped report has been generated (options derived from the response's `order_items`). |
| **RBAC — five user roles with backend authorization matrix** | done, deployed v35 / v32, migration `012_extend_user_roles` | Backend: extended `UserRole` enum (`backend/app/users/models.py`) with `director`, `production_manager`, `warehouse_manager` alongside existing `admin` / `simple_user`. Centralized role groups + `require_roles(*allowed)` dependency factory in `backend/app/dependencies.py`. Per-route guards rewritten across `customers`, `orders`, `products`, `production`, `inventory`, `reports`, `activity`, `users` routers. Service helpers `can_assign_role` / `can_manage_user` / `count_active_admins` / `is_last_active_admin` in `backend/app/users/service.py`. Pydantic `role: UserRole` rejects unknown values with 422. Self-role-change blocked (`self_role_change_denied`); self-deactivation blocked (`self_deactivation_denied`); last-active-admin demotion / deactivation blocked (`last_admin_required`); director can only assign `simple_user` (`role_assignment_denied`). Frontend: single source of truth in `frontend/src/lib/permissions.ts` (`MODULE_ACCESS`, `canAccessModule`, `canAssignRole`, `allowedRolesFor`, `ROLE_LABELS`); `requireModule(...)` / `requireRoles(...)` helpers in `frontend/src/lib/auth.ts`; sidebar / dashboard route guards filter modules per role. **Backend RBAC is authoritative** — frontend hiding is UX only; every API endpoint enforces authorization independently. Tests: `backend/tests/test_authorization_matrix.py` (51 passed, 2 skipped — last-admin guards covered directly by `test_is_last_active_admin_service_helper`). |

## RBAC matrix — load-bearing (deployed v35 / v32)

Five roles on `User.role`. **Backend is authoritative**: every API endpoint enforces authorization via `Depends(require_roles(*GROUP))` (or a tighter custom guard in `users/router.py`). The frontend's permissions table only hides UI elements the user couldn't use anyway.

| Module | admin | director (Տնօրեն) | production_manager (Արտադրության ղեկավար) | warehouse_manager (Պահեստապետ) | simple_user (Օգտատեր) |
|---|---|---|---|---|---|
| `/users` | ✓ all | ✓ list/get/create/update — sees `simple_user` only | — | — | — |
| `/orders` | ✓ | ✓ | ✓ | — | ✓ (own customer scope) |
| `/production` | ✓ | ✓ | ✓ | — | — |
| `/products` (mutations) | ✓ | ✓ | ✓ | — | read-only |
| `/inventory` (write) | ✓ | ✓ | read on `/materials` | ✓ | — |
| `/customers` | ✓ | ✓ | — | — | `/me` only |
| `/reports/sales`, `/reports/dashboard`, `/reports/inventory`, `/reports/low-stock`, `/reports/customer-discounts` | ✓ | ✓ | — | — | — |
| `/reports/production`, `/reports/material-consumption`, `/reports/damaged-stock` | ✓ | ✓ | ✓ | — | — |
| `/activity-logs` | ✓ | ✓ | — | — | — |

**Director restrictions (load-bearing):**
- Director can create or update users only when the target's role is `simple_user`. Service helper `can_manage_user(actor, target)` returns `True` only when `target.role == UserRole.simple_user`.
- Director cannot assign any role other than `simple_user`. Service helper `can_assign_role(actor, target_role)` returns `False` for all four non-`simple_user` values when actor is director.
- Director's `GET /users` is filtered server-side via `service.list_users(..., restrict_to_role=UserRole.simple_user)` so other admins / directors / managers are not enumerated.
- `GET /users/{id}` for a non-simple_user target returns 403 `user_management_denied`. The row is not leaked.

**Self-protection guards (`backend/app/users/router.py`):**
- Self-role-change (PATCH) → 403 `self_role_change_denied`.
- Self-deactivation (PATCH `is_active=false` or DELETE) → 403 `self_deactivation_denied`.
- Last-active-admin demotion (PATCH role) or deactivation (PATCH/DELETE) → 422 `last_admin_required`. Only reachable via the service helper directly because the API path is pre-empted by the self-guards (admin demoting another admin still leaves ≥ 1 active admin); covered by `test_is_last_active_admin_service_helper`.

**Smoke verification (deployed v35 / v32, 2026-05-02):**
- `GET /ready` → HTTP 200
- `GET /` (frontend) → HTTP 200
- `POST /api/v1/auth/login` (admin) → HTTP 200, `role:"admin"`
- `GET /api/v1/users?limit=20` → returned 7 rows including the original admin/simple_user accounts intact
- Frontend bundle contains the three new Armenian role labels: `Տնօրեն`, `Արտադրության ղեկավար`, `Պահեստապետ`
- Migration 012 applied (DB now contains a row with `role='director'`, only possible if the ENUM was extended)
- Plan summary: `0 to add, 3 to change, 0 to destroy` — only the three Web App / sidecontainer image references. No protected-resource changes.

**Smoke-test canary**: User ID 7 (`art@art.am`, role `director`) was created intentionally as a smoke-test canary right after v35 came online. This is the only non-original-role row in the live DB. Treat as a known canary; do not delete without coordination. The canary's existence is what makes the rollback caveat (below) bite — see `ROLLBACK_NOTES.md`.

## Partial-outcome (Խոտան) semantics — load-bearing

Stock-based `ProductionBatch` is finalized via a single endpoint with explicit per-unit quantities:

- `PATCH /production/batches/{id}/complete` body: `{good_quantity: int, damaged_quantity: int, defect_reason?: str}`.
- **No `outcome` field. No `/reject` endpoint.** The earlier whole-batch `outcome ∈ {"good","defective"}` design was replaced before merge — it cannot represent partial outcomes.
- Service-layer invariants (`backend/app/production/service.py::complete_production_batch`):
  - `good_quantity ≥ 0`
  - `damaged_quantity ≥ 0`
  - **`good_quantity + damaged_quantity == quantity_to_produce`** (strict equality — implicit shrinkage is rejected with `code="invalid_quantities"`).
- Stock effects on completion:
  - `variant.stock_quantity += good_quantity` (sellable).
  - `variant.damaged_stock_quantity += damaged_quantity` (Խոտան).
  - Materials stay deducted in all cases (defective items still consumed materials).
- Idempotent: the second `/complete` is a silent no-op (no double increment, no duplicate audit row).
- Single audit log per real transition: `production.batch_completed` with breakdown in `details`.

UI surfaces:

- **Production page** (`/dashboard/production`): each batch row shows the `BatchControl` form with `Լավ` / `Խոտան` number inputs + "Բոլորը լավ" / "Բոլորը Խոտան" shortcuts; the `Ավարտել` button is disabled until the sum equals `quantity_to_produce`. After completion, the row shows `Լավ՝ N · Խոտան՝ M` (with red badge and `defect_reason` tooltip when M > 0).
- **Products / Ապրանքներ page** (admin and non-admin variant tables): a `Խոտան` column is displayed *always*, next to `Մնացորդ`. Red text when > 0, gray-400 when 0.
- **Reports / Հաշվետվություններ** (`/dashboard/reports`): new report type `Խոտանի հաշվետվություն` with three summary cards (`Ընդհանուր խոտան`, `Ապրանքների քանակ`, `Տարբերակների քանակ`) and a per-variant table. JSON + CSV export. Backed by `GET /reports/damaged-stock`.

Order-based production damaged tracking is **NOT implemented** — it is Phase 2 and remains explicitly off the roadmap until the open product question is answered. See `NEXT_TASKS.md`.

## Rolled back / removed (do not restore)

- Migration `009_production_stage_rewrite` — removed in an earlier emergency rollback. See `ROLLBACK_NOTES.md`.
- Whole-batch `outcome` / `defect_reason` design from the first 010 attempt (revision `010_batch_outcome.py`) — replaced before merge by the partial-outcome design above. Do not reintroduce a single-outcome enum on `ProductionBatch`.
- The "production stage rewrite" code path that lived alongside `009`. Production now uses the legacy `ProductionStage` rows + the new aggregation endpoints, not a rewritten table.

## Tests

- Backend: `docker-compose exec backend pytest tests/ -q` → **79 passed** (most recent run, this snapshot).
  - 13 in `test_production_batches.py` (cover whole-good, all-damaged, partial, idempotence, sum-equality, negative-quantity rejection, materials kept deducted, single audit log).
  - 7 in `test_reports_damaged_stock.py` (cover empty, partial-complete, multi-batch aggregation, zero-damaged exclusion, CSV export, existing-report smoke, sellable-vs-damaged separation).
  - All other prior tests unchanged.
- Frontend type check: `docker-compose exec frontend npx tsc --noEmit` → exit 0.
- Frontend build: `docker-compose exec frontend npm run build` → 17/17 pages compile.
- Cyrillic/Greek scan on touched frontend files → 0 matches.

## Untracked artifacts on disk (not committed, safe to gitignore)

- `backend/celerybeat-schedule` — Celery beat runtime state.
- `backend/test.db` — SQLite test DB written by pytest.
- `frontend/tsconfig.tsbuildinfo` — TypeScript incremental build cache.

These should not be added to git; recommend appending to `.gitignore` in a follow-up.
