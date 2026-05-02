# Next Tasks

State of each in-flight workstream. "Done" means landed in the current commit on `v12`. "Open" means the user has asked but it's not yet implemented (or is partial). "Watch" means no action requested but the area has known follow-ups.

## Done (in commit `ef49b8d`)

### Production page — one row per order (Option B)
- API aggregation only. **No DB migration. No model change.**
- New: `GET /production?one_per_order=true&active=true&status=...&page=...&limit=...`
- New: `PATCH /production/orders/{order_id}/current` — takes `{stage, status, note?}`, enforces single-in-progress invariant, writes one `ActivityLog` per real change (action `production.order_current_changed`).
- Helpers in `backend/app/production/service.py`: `compute_current(rows)`, `get_stages_for_order(...)`, `list_one_per_order(...)`, `set_order_current(...)`.
- Frontend: `frontend/src/app/dashboard/production/OrderCurrentControl.tsx` (replaces the old per-row `StageStatusChange` on the list page). Sewing label is `Մշակում` everywhere.
- Tests: 15 new in `backend/tests/test_production_orders.py`. All 65 backend tests pass.
- Legacy per-row endpoints (`PATCH /production/{stage_id}`) kept for backward compatibility.
- Future watch: see "Production page one-row-per-order — fragile invariant" in `KNOWN_RISKS.md` #5.

### Order item display
- `OrderItemResponse` now nests `product_variant: OrderItemVariantBrief` (which itself nests `product: OrderItemProductBrief`).
- `ProductVariant.product` relationship now `lazy="selectin"` so the data loads with the item.
- Order detail page renders `<ProductName>` on line 1 and `Չափս: <size> · Գույն: <color>` on line 2 (fallback to `Տարբերակ #N` only when variant is null).
- Frontend types in `frontend/src/types/models.ts` mirror the new schema.

### Product image gallery
- New component `frontend/src/components/products/ProductImageGallery.tsx` — main image + horizontal thumbnail strip + lightbox modal with `← / → / Esc` keyboard navigation. Sorts primary first, then by id. `console.warn` for missing URLs (never silently hidden).
- Used by `/catalog/[id]` (full size) and `/dashboard/products/[id]` non-admin branch (`mainHeightClass="h-64"`).
- Admin branch of product detail still uses `ProductImageUpload` (untouched).

### Homepage hardcoded translations — removed
- `frontend/src/components/home/FeaturedProducts.tsx` no longer contains the three `Record<string, string>` translation maps or the `t()` helper. Renders `product.category?.name`, `product.name`, `product.description` straight from the API, matching `/catalog`.
- Whatever language sits in the DB is what the homepage now displays.
- **Rule for the future:** do not reintroduce frontend-side data translation maps without explicit approval (see `SAFE_TASK_RULES.md` #6).

### Audit log
- ~25 mutation events audited across orders, products, inventory, production, users, customers, reports.
- Admin-only page at `/dashboard/activity` with Armenian action labels (`ACTION_LABELS` in `frontend/src/app/dashboard/activity/page.tsx`).
- Sensitive data (passwords, hashes, tokens) is never written into `old_values`/`new_values` — uses `details=` strings instead.
- Migration `008_activity_log_columns` is the latest applied head.

### Stock-based production (batches)
- `ProductionBatch` model + endpoints + worker-side material deduction and stock add-on-completion.
- Migration `007_production_batches`.
- Tests in `backend/tests/test_production_batches.py` cover the deduction-once and stock-once invariants.

## Done (deployed v34 / v31, this commit)

### Sales report — per-customer + per-order filtering and export

`GET /api/v1/reports/sales` now accepts:

- `customer_id` *(optional)* — scopes the report to one customer. Response carries a `selected_customer` block and a per-OrderItem `order_items` list (revenue-eligible orders only). 404 `customer_not_found` if missing.
- `order_id` *(optional, requires `customer_id`)* — scopes the report further to one order belonging to that customer. Response carries a `selected_order` block (`{id, order_date, status}`).
  - `order_id` without `customer_id` → **422 `order_id_requires_customer_id`**.
  - `order_id` for a missing order → **404 `order_not_found`**.
  - `order_id` for an order belonging to a different customer → **422 `order_not_for_customer`**.

`format=csv` filename derived from the filter combination:

| Filters | Filename |
|---|---|
| (none) | `sales_report.csv` |
| `customer_id` | `customer-report-<slug>-<YYYY-MM-DD>.csv` |
| `customer_id` + `order_id` | `customer-report-<slug>-order-<id>-<YYYY-MM-DD>.csv` |

`<slug>` is computed by `service.customer_filename_slug(name, customer_id)` — lowercased, ASCII-only `[a-z0-9-_]`; spaces become `-`; non-ASCII (incl. Armenian) is dropped; falls back to `customer-{id}` when the cleaned slug is empty.

Frontend (`frontend/src/app/dashboard/reports/ReportBuilder.tsx`):

- Customer dropdown is shown for the `orders` and `sales` reports (`CUSTOMER_FILTER_REPORTS` set).
- For `sales` only, an additional **Պատվեր** dropdown appears once a customer has been selected *and* a customer-scoped report has been generated. Options come from the response's `order_items` (unique `(order_id, order_date)` pairs, sorted by id desc). The dropdown stays populated across order-filtered regenerations so the user can switch between orders without re-fetching the customer list.
- Switching customer or report type clears both `orderFilter` and `customerOrders`.
- The selected-customer header card now shows a sub-line "Ընտրված պատվեր: #N · YYYY-MM-DD · status" when an order is selected.

Audit log: `report.generated` / `report.exported` rows now include `order_id` in `new_values.filters` for sales-report calls.

Tests: `backend/tests/test_reports_sales.py` — 11 cases (6 from the previous customer-only task + 5 new for `order_id`: customer+order returns only that order, CSV filename includes `-order-<id>-`, missing customer_id → 422, ownership mismatch → 422, missing order_id → 404).

No DB migration. Alembic head remains `011_order_stock_deducted`.

#### Rollback (per-customer + per-order export → previous live)

The previous live tags are still in the registry; rollback is a one-step Terraform apply.

1. Edit `terraform/envs/dev/terraform.tfvars`:
   ```
   backend_image_tag  = "v33"
   frontend_image_tag = "v30"
   ```
2. From `terraform/envs/dev/`:
   ```bash
   source .env.terraform
   terraform plan -out=tfplan
   ```
   Expected plan: **0 to add, 3 to change, 0 to destroy** — `azapi_resource.backend_main`, `azapi_resource.backend_worker[0]`, `azurerm_linux_web_app.frontend` revert to v33 / v30. Verify the plan shows **no** changes to the four protected data resources (PostgreSQL server / database, Storage Account / container) or the two `azurerm_management_lock` resources.
3. `terraform apply tfplan` (~40–80 s).
4. Smoke check:
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw frontend_url)/"
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw backend_url)/ready"
   terraform output | grep -E "deployed_image|backend_image"  # → v30 / v33
   ```

**No DB rollback needed** — this task added no migration. Cookies issued by v34 are still valid against v33 (same `backend_secret_key`). v33 backend ignores any leftover `order_id` query string from a stale v31 frontend page; v30 frontend won't render the order dropdown so the parameter is never sent.

## Done (in working tree, not yet committed)

### Phase 1 — Stock-based production: partial outcome (Խոտան)
- Migration `010_batch_partial_outcome` adds `good_quantity`, `damaged_quantity`, `defect_reason` to `production_batches` and `damaged_stock_quantity` to `product_variants`. INT/TEXT only — no enum, no CAST.
- Migration verified end-to-end on a clean Postgres DB; downgrade reverses cleanly.
- Single endpoint: `PATCH /production/batches/{id}/complete` body `{good_quantity, damaged_quantity, defect_reason?}`. Strict invariant `good + damaged == quantity_to_produce` (no implicit shrinkage).
- `variant.stock_quantity += good_quantity`; `variant.damaged_stock_quantity += damaged_quantity`. Materials stay deducted regardless of outcome.
- Idempotent: second `/complete` is a silent no-op.
- Old whole-batch `outcome` / `defect_reason` schema and `/reject` endpoint were replaced before merge — do not reintroduce.
- Frontend: `BatchControl.tsx` now an inline form (Լավ + Խոտան number inputs, "Բոլորը լավ" / "Բոլորը Խոտան" shortcuts, sum validated client-side). Production list shows `Լավ՝ N · Խոտան՝ M` after completion. Products page (admin + non-admin) shows `Խոտան` column always.
- Tests: 13 in `test_production_batches.py`; 2 pre-existing `/complete` call sites in `test_activity.py` and `test_production_orders.py` updated to send the new body.

### Damaged-stock report (Խոտանի հաշվետվություն)
- New endpoint `GET /reports/damaged-stock` (json + csv) with `_audit_report` integration.
- Returns `{summary: {total_damaged, products_affected, variants_affected}, items: [...]}`. Lists only variants with `damaged_stock_quantity > 0`.
- `ReportBuilder.tsx` got a new report type (`Խոտանի հաշվետվություն`), columns config, and a custom `DamagedStockPreview` (three summary cards + per-variant table). No changes to existing reports.
- Tests: 7 in `backend/tests/test_reports_damaged_stock.py` (covers empty, partial-complete reflected, multi-batch aggregation, zero-damaged exclusion, CSV, existing-report smoke, sellable-vs-damaged separation).

## Open

### Phase 2 — Order-based production: damaged outcome
**Not started. Blocked on a product decision.**

Order-based production today has no completion step that touches stock. Materials are deducted at order confirmation; `production_quantity` is recorded on each `OrderItem`; `ProductionStage` rows drive the UI workflow but don't increment any counter. The "produced" items go directly to the order, never into general `stock_quantity`.

Adding partial outcome to order-based production therefore requires designing a new completion semantic. If 5 of 7 ordered units come out good and 2 damaged:
- The 2 damaged → `variant.damaged_stock_quantity` (clear).
- The 5 good → fulfill the order; do NOT add to general sellable stock (they're earmarked).
- The order is now short by 2. **Three possible behaviors, all reasonable, none implicit:**
  - **(a) Auto-create a re-production batch** for the missing 2 units. Conservative; keeps the order whole without admin action.
  - **(b) Mark the order partially fulfilled** and let admin decide — re-produce, or ship short with a note to the customer.
  - **(c) Ship short**, set an explicit `OrderItem.shortfall_quantity`, requires customer comms.

**Required before Phase 2 implementation:**
- Pick (a) / (b) / (c) — this is a product decision, not a code decision.
- Decide where in the production-stage workflow per-item outcome gets entered (after QC? at ready-for-shipment? per stage transition?).
- Decide whether `OrderItem` needs a new column (e.g. `damaged_quantity_produced INT NOT NULL DEFAULT 0` and possibly `shortfall_quantity` if (c) is chosen).
- Cyrillic/Greek scan + tsc + build + Cyrillic-aware tests follow normal `SAFE_TASK_RULES.md` procedure.

Until then, treat order-based damaged production as **off the roadmap** — do not implement parts of it speculatively. The Phase 1 stock-based design is intentionally separate.

## Done — Azure deployment milestones

### Phase 4 — Azure Blob Storage (replaces MinIO sidecar in Azure)
- `backend/app/storage/azure_adapter.py` is **implemented** (was a placeholder in earlier snapshots). Uses `azure-storage-blob==12.23.1` + `azure-identity==1.19.0` (added in C2a).
- Storage Account `startdevimgsart4242` (Standard_LRS, StorageV2, Hot) and private container `art-images` are managed by Terraform in `terraform/envs/dev/main.tf`. **`shared_access_key_enabled = false`** since Task C2b — only Entra ID/Managed Identity tokens are accepted.
- Backend image proxy `/api/v1/products/images/file/{key}` is **backend-agnostic** — uses `storage.download_file()` against the abstraction, works with both MinIO (local) and Azure Blob (deployed). v20 backend was MinIO-only and 404'd in Azure for image GETs; v30 is the current live backend tag.
- Default `STORAGE_BACKEND=azure` for deployed envs; `minio` for local docker-compose. `minio_sidecar_enabled = false` is the default in Terraform; the sitecontainer block remains for parity but is disabled. **Never enable MinIO in Azure** — it's local-dev-only.

### Tasks A / B / C — Security hardening (done)

#### Task A — Critical credentials hardening (deployed v25)
- `WEAK_SECRET_KEYS` validator in `backend/app/config.py` refuses placeholder/short keys when `APP_ENV=production`. `terraform/envs/dev/variables.tf` has the matching validation on `var.backend_secret_key`.
- FastAPI docs (`/docs`, `/redoc`, `/openapi.json`) are gated by `_docs_kwargs` helper in `backend/app/main.py` — disabled in production.
- Seed script (`backend/scripts/seed.py`) refuses to run in production unless `ENABLE_SEED_DATA=1` AND `ADMIN_INITIAL_PASSWORD` is non-default.
- Tests: `backend/tests/test_security_hardening.py`.

#### Task B — Auth surface hardening (deployed v28)
- slowapi rate limit: 5/min on `/auth/login`, 20/min on `/auth/refresh`. `_client_ip` key reads `X-Forwarded-For`, strips the ephemeral source port Azure App Service prepends to each entry, falls back to `request.client.host`. `headers_enabled=False` on Limiter to avoid `_inject_headers` raising on dict-return endpoints.
- `OriginCheckMiddleware` (`backend/app/origin_check.py`) blocks `POST/PUT/PATCH/DELETE` with bad/missing `Origin`/`Referer` — defends against CSRF.
- Backend container runs as non-root `app:1001` (`backend/Dockerfile.azure`).
- Tests: `backend/tests/test_auth_surface_hardening.py` (Origin checks + `_client_ip` port-stripping + rate-limit wiring).
- v26 (slowapi `headers_enabled=True` bug) and v27 (missing port-strip) are blacklisted in `terraform/envs/dev/variables.tf`.

#### Task C1 — PostgreSQL least-privilege runtime user (deployed v29)
- `backend/scripts/bootstrap_db_user.py` runs from `entrypoint.sh` AFTER Alembic and BEFORE uvicorn. Idempotent: creates `art_app` if missing, `ALTER ROLE art_app WITH PASSWORD <ART_APP_DB_PASSWORD>`, then re-grants `CONNECT` on the database, `USAGE` on schema `public`, `SELECT/INSERT/UPDATE/DELETE` on tables and sequences, plus `ALTER DEFAULT PRIVILEGES` for future objects.
- Runtime `DATABASE_URL` connects as `art_app` (CRUD only, no DDL, no role management).
- `DATABASE_URL_SYNC` retains the `art_admin` admin for Alembic + bootstrap. After Alembic + bootstrap finish, uvicorn uses the runtime DSN; the admin DSN is no longer accessed.
- Terraform: `random_password.art_app_db` (24-char URL-safe), `ART_APP_DB_PASSWORD` app setting, `postgres_app_password` output (sensitive).
- Tests: `backend/tests/test_db_bootstrap.py` (gate logic, password validator, role-name lock-in, source scan for hardcoded passwords).

#### Task C2a — Storage Managed Identity (deployed v30)
- Backend Web App has `identity { type = "SystemAssigned" }` (principal_id `8b108e0c-10af-4d3d-9a34-5f372f684064`).
- Granted `Storage Blob Data Contributor` on the storage account scope via `azurerm_role_assignment.backend_blob_data_contributor[0]`.
- Backend adapter (`backend/app/storage/azure_adapter.py`) selects auth path at `__init__`: MI when `AZURE_STORAGE_ACCOUNT_URL` is set, else connection string. New dependency: `azure-identity==1.19.0`.
- Two-stage apply pattern: `var.enable_storage_role_assignment` (default `false`) gates the role assignment so the planner doesn't fail on `identity[0]` being null when adding identity to an existing Web App. The dev env's `terraform.tfvars` sets it to `true` post-bootstrap.
- Tests: `backend/tests/test_storage_managed_identity.py` (auth-mode branch logic, settings field).

#### Task C2b — Storage shared-key denial
- `AZURE_STORAGE_CONNECTION_STRING` removed from backend `app_settings` in `main.tf`.
- `azurerm_storage_account.images.shared_access_key_enabled = false` — shared-key auth blocked at the data plane.
- Provider configured with `storage_use_azuread = true` in `providers.tf` so `terraform plan` can read storage account data-plane sub-properties (`queue_properties`, etc.) via the SP's Entra ID token instead of shared keys. The SP must hold a Storage data-plane role (currently inherited from subscription Owner). If SP is downgraded, grant `Storage Blob Data Owner` on the storage account explicitly.
- Live verification: end-to-end image upload + read + delete succeed via MI (MD5 round-trip match), 404 on deleted blob.

### Phase 5 — Multi-image product gallery
- `frontend/src/components/products/ProductCardImage.tsx` (new) — card-sized clickable thumbnail with built-in fullscreen lightbox (prev/next/thumbnails, Esc/←/→ keyboard, "+N" badge, Armenian aria-labels). Used by the catalog page and the homepage `FeaturedProducts`.
- `ProductImageGallery.tsx` already existed for product detail pages — kept.
- Backed by the existing `ProductImage` schema and `_populate_image_urls` helper. **No DB migration.** Alembic head remains `010_batch_partial_outcome`.

### Phase 5b — Production modal product dropdown defensive fetch
- `frontend/src/app/dashboard/production/CreateBatchModal.tsx` now tracks loading/error/empty states, attempts a single silent `/api/v1/auth/refresh` on 401 (covers the case where the access_token expired between SSR render and modal open), exposes a "Կրկին փորձել" retry button, and uses `Array.isArray(data?.items)` defensively.
- Live in `art-frontend:v24`.

### Image tag history (Azure deployment)

Live: `art-frontend:v24`, `art-backend:v30`. Blacklisted in `terraform/envs/dev/variables.tf` validation:

| Tag | Reason retired |
|---|---|
| `art-backend:v13` | Failed migration `009`; the boot guard exists to recover from it. See `KNOWN_RISKS.md` #2. |
| `art-backend:v26` | Task B regression: slowapi `headers_enabled=True` + dict-return endpoints raised inside `_inject_headers`, short-circuiting the rate limiter. |
| `art-backend:v27` | Task B regression: missing XFF port-strip; Azure App Service prepends ephemeral source ports to each XFF entry, so every request landed in a fresh rate-limit bucket and the limit never fired. |
| `art-frontend:v21` | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed in Azure with `Module parse failed: Unexpected character '@'` on Tailwind globals.css under `NODE_ENV=production`. Always use `frontend/Dockerfile.azure` for production builds. |
| `art-frontend:v22` and `v23` | Built from Git Bash on Windows without `MSYS_NO_PATHCONV=1`; MSYS rewrote `--build-arg NEXT_PUBLIC_API_URL=/api/v1` to `C:/Program Files/Git/api/v1`, which webpack inlined into every `clientFetch` call. Every browser-side fetch threw `TypeError: Failed to fetch`. SSR was unaffected. v22 was the symptomless variant; v23 surfaced the bug because its modal's defensive logic exposed it. See `KNOWN_RISKS.md` #8. |

Backend tag lineage (live progression):
- `v21` → `v25` (Task A) → `v28` (Task B) → `v29` (Task C1) → `v30` (Task C2a/b — current).
- v25, v28, v29 are retired but not blacklisted; rolling back to one of them to triage a new regression is permitted (would temporarily restore connection-string auth + admin-as-runtime-DB-user, both undesirable).

When publishing a new frontend tag from Git Bash on Windows, **always** set `MSYS_NO_PATHCONV=1` and verify the bundle is clean before pushing — see CLAUDE.md "Building Docker images on Windows / Git Bash" for the verification command.

## Watch (no action, but follow-ups exist)

- **`.gitignore` cleanup** — `backend/celerybeat-schedule`, `backend/test.db`, `frontend/tsconfig.tsbuildinfo` are runtime/build artifacts that show up as untracked on every commit. Adding them to `.gitignore` is a one-line follow-up.
- **`v12` branch is 1 commit ahead of `origin/v12`** — not pushed, not merged. Push only on explicit request.
- **`hoso30/art-backend:v13` cached image is poisoned** — see `KNOWN_RISKS.md` #2 and `ROLLBACK_NOTES.md`. Any future backend image publish must be a fresh build with `--no-cache`.
- **Local main Postgres DB stamp is stale** — `art_manufacturing` is stamped at `006_order_item_fulfillment` but the schema already contains 007/008 tables (an artifact of the v13 rollback). `alembic upgrade head` against it fails with `DuplicateTable`. Migration 010 itself is fine; verified on a clean temp DB. Local fix would be `UPDATE alembic_version SET version_num = '008_activity_log_columns'` but explicit approval is required before writing to the main local DB. Azure deploys against the Flexible Server run all migrations cleanly because that DB was created fresh.
- **PostgreSQL is in North Europe** while every other resource is in West Europe (`LocationIsOfferRestricted` exception). When the West Europe block is lifted, set `postgres_location = "West Europe"` in tfvars and re-apply (recreates the server — `pg_dump` first if there is data to keep).
- **Service Principal is currently Owner; downgrading needs RBAC follow-up** — Owner was elevated for Task C2a (role-assignment creation) and is currently retained because `storage_use_azuread = true` (set in C2b) needs the SP to have a Storage data-plane role to read storage sub-properties on every plan. If you downgrade the SP back to Resource Manager `Contributor`, grant explicit `Storage Blob Data Owner` on `azurerm_storage_account.images` first, or `terraform plan` will start 403'ing. Either way, document the elevation event here and in `handoff/SAFE_TASK_RULES.md` "Service Principal role for Terraform".
- **`storage_account_connection_string` output still exists** — kept for break-glass debugging. Even with `shared_access_key_enabled = false`, the output embeds the storage account access key (still present in the resource for control-plane purposes). Treat as sensitive. **Future hardening: remove the output entirely** once nothing in the workflow needs it. Tracking: see `terraform/envs/dev/outputs.tf`.
- **24h soak after C2b** — backend is now MI-only for blob auth. Watch for any 5xx on `/api/v1/products/images/file/{key}` over the next 24h that could indicate transient MI token issues. None observed in initial verification.

## Explicitly not on the roadmap (do not start)

- A new `009_*` migration of any kind, especially anything touching `ProductionStage` or its enums. See `KNOWN_RISKS.md` #1.
- Reintroducing the production-stage rewrite code path (`StageStatusChange.tsx` rewrite version, the `set_stage_status` rewrite branch, etc.).
- Removing the entrypoint migration guard. See `KNOWN_RISKS.md` #3.
- Adding hardcoded Armenian translation maps for any data that comes from the API.
- Re-introducing a whole-batch `outcome` enum on `ProductionBatch`, or a separate `/reject` endpoint. The partial-quantity design is the canonical Khotan model — see `CURRENT_STATE.md` "Partial-outcome (Խոտան) semantics" section.
- Mixing `damaged_stock_quantity` into sellable-stock reads (catalog, order fulfillment, inventory totals). Damaged stock is a separate counter; treating it as available for sale would corrupt customer-visible inventory.
- Order-based damaged production work without first answering the (a)/(b)/(c) product question above.
