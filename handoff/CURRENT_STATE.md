# Current State

Snapshot as of the most recent verified working tree on `v12`. Future agents: confirm each line by running the listed verification command before relying on it — this file ages.

## Azure deployment — currently live

| Component | State | Live value |
|---|---|---|
| Resource group | applied | `rg-art-dev` (West Europe) |
| Frontend Web App | applied, serving | `app-art-frontend-dev-art4242` on `asp-art-dev` (F1 Free) — image `hoso30/art-frontend:v24` |
| Backend Web App | applied, serving | `app-art-backend-dev-art4242` on `asp-art-backend-dev` (F1 Free) — image `hoso30/art-backend:v21` |
| Backend `worker` sidecar | applied | image `hoso30/art-backend:v21`, running Celery worker + beat |
| Backend `redis` sidecar | applied | `redis:7-alpine`, internal-only |
| Backend `minio` sidecar | disabled | `minio_sidecar_enabled = false` since Phase 4. Sitecontainer resource still exists in `main.tf` for parity. |
| PostgreSQL Flexible Server | applied, serving | `psql-art-dev-art4242` (B_Standard_B1ms, PG 16, 32 GB, 7-day backup, **North Europe** — see PostgreSQL exception in CLAUDE.md) |
| Storage Account | applied | `startdevimgsart4242` (Standard_LRS, StorageV2, Hot) |
| Blob container | applied | `art-images` (private) — browsers fetch via backend `/api/v1/products/images/file/{key}` proxy |
| Cost target | preserved | $0/month while the 12-month free tier is active |
| Data protection | enforced | All four data resources (`azurerm_postgresql_flexible_server.this`, `…_database.app`, `azurerm_storage_account.images`, `azurerm_storage_container.images`) carry `lifecycle { prevent_destroy = true }`. Two `azurerm_management_lock` resources (`postgres_no_delete`, `storage_no_delete`) hold `CanNotDelete` Azure-side locks scoped to the server and the storage account; locks inherit to the database and the container. See `handoff/KNOWN_RISKS.md` #10 and `handoff/SAFE_TASK_RULES.md` "Critical Data Protection". |
| Terraform SP role | Contributor only | The SP at `ARM_CLIENT_ID` (in `terraform/envs/dev/.env.terraform`) holds **Contributor** at subscription scope. Sufficient for all day-to-day operations (image bumps, app settings, password rotations, firewall rules). Owner was granted **temporarily** to create the two `azurerm_management_lock` resources, then revoked. **Re-grant Owner (or a narrow custom role with `Microsoft.Authorization/locks/*`) only when changing the locks** — see `handoff/SAFE_TASK_RULES.md` "Service Principal role for Terraform". |

Verify image tags after any apply:

```bash
cd terraform/envs/dev
source .env.terraform
terraform output | grep -E "deployed_image|backend_image"
# deployed_image = "hoso30/art-frontend:v24"
# backend_image  = "hoso30/art-backend:v21"
```

Full topology and verification commands: see `AZURE_DEPLOYMENT.md`. Variable reference and free-tier rules: see `terraform/envs/dev/README.md`.

## Branch and commit

- Active branch: `v12` (1 commit ahead of `origin/v12`, not pushed, not merged).
- Most recent committed work: `ef49b8d` — "Production rewrite, order/product UX fixes, and homepage cleanup".
- Uncommitted in working tree: Phase 1 Խոտան (partial-outcome) feature + damaged-stock report. Not yet committed at the time this snapshot was written.
- Verify: `git log --oneline -5` and `git status --short`.

## Alembic head

- Current head: **`010_batch_partial_outcome`** (down-revision `008_activity_log_columns`).
- Migration files on disk (`backend/alembic/versions/`):
  - `001_initial`
  - `002_var_mat_req`
  - `003_user_discount`
  - `004_order_materials_deducted`
  - `006_order_item_fulfillment`  *(no 005 file — intentional, it was removed during an earlier rollback)*
  - `007_production_batches`
  - `008_activity_log_columns`
  - `010_batch_partial_outcome`  *(no 009 file — see `KNOWN_RISKS.md` #1)*
- **No `009_*` migration exists. It must not be reintroduced — see `KNOWN_RISKS.md` #1.**
- Verify: `ls backend/alembic/versions/` and `docker-compose exec backend alembic current`.

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
 010_batch_partial_outcome}
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
| Storage abstraction (MinIO local, Azure Blob deployed) | done | `backend/app/storage/` — `interface.py`, `minio_adapter.py`, `azure_adapter.py` (real, not a placeholder). `STORAGE_BACKEND=minio` for compose, `azure` for deployed envs. |
| Multi-image product gallery (Phase 5) | done | `frontend/src/components/products/ProductCardImage.tsx`, `ProductImageGallery.tsx`. Clickable card → fullscreen lightbox with prev/next/thumbnails/Esc/←/→ keyboard nav. Backed by existing `ProductImage` schema (no migration). |
| Backend image proxy (backend-agnostic) | done | `backend/app/products/router.py::stream_image_file` reads via `storage.download_file()` so the same code path works against MinIO and Azure Blob. v21 fix; v20 was MinIO-only. |
| Production page: one row per order (Option B, API aggregation, no migration) | done in `ef49b8d` | `GET /production?one_per_order=true`, `PATCH /production/orders/{id}/current`, `OrderCurrentControl.tsx` |
| Order detail items: product name + size/color | done in `ef49b8d` | `OrderItemResponse.product_variant`, `frontend/src/app/dashboard/orders/[id]/page.tsx` |
| Product image gallery (thumbnails + lightbox) | done in `ef49b8d` | `frontend/src/components/products/ProductImageGallery.tsx` |
| Homepage hardcoded translations removed | done in `ef49b8d` | `frontend/src/components/home/FeaturedProducts.tsx` |
| **Stock-based production: partial outcome (Խոտան)** | **done in working tree, migration `010`** | `backend/app/production/{models,schemas,service,router}.py`, `backend/app/products/{models,schemas}.py`, `BatchControl.tsx`, `frontend/src/app/dashboard/production/page.tsx`, `VariantActions.tsx`, `frontend/src/app/dashboard/products/[id]/page.tsx` |
| **Damaged-stock report (Խոտանի հաշվետվություն)** | **done in working tree** | `backend/app/reports/{service,router}.py`, `frontend/src/app/dashboard/reports/ReportBuilder.tsx`, `backend/tests/test_reports_damaged_stock.py` |

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
