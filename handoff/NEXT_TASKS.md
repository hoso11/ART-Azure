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
- `backend/app/storage/azure_adapter.py` is **implemented** (was a placeholder in earlier snapshots). Uses `azure-storage-blob==12.23.1`.
- Storage Account `startdevimgsart4242` (Standard_LRS, StorageV2, Hot) and private container `art-images` are managed by Terraform in `terraform/envs/dev/main.tf`.
- Backend image proxy `/api/v1/products/images/file/{key}` is **backend-agnostic** — uses `storage.download_file()` against the abstraction, works with both MinIO (local) and Azure Blob (deployed). v20 backend was MinIO-only and 404'd in Azure for image GETs; v21 is the live backend tag.
- Default `STORAGE_BACKEND=azure` for deployed envs; `minio` for local docker-compose. `minio_sidecar_enabled = false` is the default in Terraform; the sitecontainer block remains for parity but is disabled.

### Phase 5 — Multi-image product gallery
- `frontend/src/components/products/ProductCardImage.tsx` (new) — card-sized clickable thumbnail with built-in fullscreen lightbox (prev/next/thumbnails, Esc/←/→ keyboard, "+N" badge, Armenian aria-labels). Used by the catalog page and the homepage `FeaturedProducts`.
- `ProductImageGallery.tsx` already existed for product detail pages — kept.
- Backed by the existing `ProductImage` schema and `_populate_image_urls` helper. **No DB migration.** Alembic head remains `010_batch_partial_outcome`.

### Phase 5b — Production modal product dropdown defensive fetch
- `frontend/src/app/dashboard/production/CreateBatchModal.tsx` now tracks loading/error/empty states, attempts a single silent `/api/v1/auth/refresh` on 401 (covers the case where the access_token expired between SSR render and modal open), exposes a "Կրկին փորձել" retry button, and uses `Array.isArray(data?.items)` defensively.
- Live in `art-frontend:v24`.

### Image tag history (Azure deployment)

Live: `art-frontend:v24`, `art-backend:v21`. Blacklisted in `terraform/envs/dev/variables.tf` validation:

| Tag | Reason retired |
|---|---|
| `art-backend:v13` | Failed migration `009`; the boot guard exists to recover from it. See `KNOWN_RISKS.md` #2. |
| `art-frontend:v21` | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed in Azure with `Module parse failed: Unexpected character '@'` on Tailwind globals.css under `NODE_ENV=production`. Always use `frontend/Dockerfile.azure` for production builds. |
| `art-frontend:v22` and `v23` | Built from Git Bash on Windows without `MSYS_NO_PATHCONV=1`; MSYS rewrote `--build-arg NEXT_PUBLIC_API_URL=/api/v1` to `C:/Program Files/Git/api/v1`, which webpack inlined into every `clientFetch` call. Every browser-side fetch threw `TypeError: Failed to fetch`. SSR was unaffected. v22 was the symptomless variant; v23 surfaced the bug because its modal's defensive logic exposed it. See `KNOWN_RISKS.md` #8. |

When publishing a new frontend tag from Git Bash on Windows, **always** set `MSYS_NO_PATHCONV=1` and verify the bundle is clean before pushing — see CLAUDE.md "Building Docker images on Windows / Git Bash" for the verification command.

## Watch (no action, but follow-ups exist)

- **`.gitignore` cleanup** — `backend/celerybeat-schedule`, `backend/test.db`, `frontend/tsconfig.tsbuildinfo` are runtime/build artifacts that show up as untracked on every commit. Adding them to `.gitignore` is a one-line follow-up.
- **`v12` branch is 1 commit ahead of `origin/v12`** — not pushed, not merged. Push only on explicit request.
- **`hoso30/art-backend:v13` cached image is poisoned** — see `KNOWN_RISKS.md` #2 and `ROLLBACK_NOTES.md`. Any future backend image publish must be a fresh build with `--no-cache`.
- **Local main Postgres DB stamp is stale** — `art_manufacturing` is stamped at `006_order_item_fulfillment` but the schema already contains 007/008 tables (an artifact of the v13 rollback). `alembic upgrade head` against it fails with `DuplicateTable`. Migration 010 itself is fine; verified on a clean temp DB. Local fix would be `UPDATE alembic_version SET version_num = '008_activity_log_columns'` but explicit approval is required before writing to the main local DB. Azure deploys against the Flexible Server run all migrations cleanly because that DB was created fresh.
- **PostgreSQL is in North Europe** while every other resource is in West Europe (`LocationIsOfferRestricted` exception). When the West Europe block is lifted, set `postgres_location = "West Europe"` in tfvars and re-apply (recreates the server — `pg_dump` first if there is data to keep).

## Explicitly not on the roadmap (do not start)

- A new `009_*` migration of any kind, especially anything touching `ProductionStage` or its enums. See `KNOWN_RISKS.md` #1.
- Reintroducing the production-stage rewrite code path (`StageStatusChange.tsx` rewrite version, the `set_stage_status` rewrite branch, etc.).
- Removing the entrypoint migration guard. See `KNOWN_RISKS.md` #3.
- Adding hardcoded Armenian translation maps for any data that comes from the API.
- Re-introducing a whole-batch `outcome` enum on `ProductionBatch`, or a separate `/reject` endpoint. The partial-quantity design is the canonical Khotan model — see `CURRENT_STATE.md` "Partial-outcome (Խոտան) semantics" section.
- Mixing `damaged_stock_quantity` into sellable-stock reads (catalog, order fulfillment, inventory totals). Damaged stock is a separate counter; treating it as available for sale would corrupt customer-visible inventory.
- Order-based damaged production work without first answering the (a)/(b)/(c) product question above.
