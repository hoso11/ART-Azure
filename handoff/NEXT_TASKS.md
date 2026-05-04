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

## Done (deployed v36 / v33, this commit)

### Bulk / series production batch creation (Շարք)

Admin can now create multiple `ProductionBatch` rows in a single request from the `Նոր արտադրություն` modal. The single-create path is unchanged.

**Backend API.** New endpoint `POST /api/v1/production/batches/bulk` (gate: `BUSINESS_MANAGER` — admin / director / production_manager). Request: `{product_id, items: [{variant_id, quantity_to_produce}]}`. Response: `{items: [<ProductionBatchResponse>]}`.

**Atomic, all-or-nothing.** Service `create_production_batches_bulk` (in `backend/app/production/service.py`) validates everything before any DB write:

- Pydantic-level: `1 <= len(items) <= 50`, no duplicate `variant_id`, `quantity_to_produce >= 1`.
- Variant-belongs-to-product check via a single `SELECT … FOR UPDATE`.
- Size-keyed `ProductSizeMaterialRequirement` rows must exist for every variant size.
- Materials are aggregated across the whole request (`material_id → SUM(qty_per_item * quantity_to_produce)`) and the aggregated requirement is checked against `Inventory` once.
- If any check fails: `ValidationException` rolls back the whole transaction — no batches, no stock movements.
- If checks pass: one `StockMovement` per material (with the *summed* deduction; reason `stock_based_production` — same as single-create, no ENUM change), then one `ProductionBatch` per item with the existing defaults.
- Router emits one `production.batch_created` audit row per created batch — identical shape to N single-creates.

**No DB migration.** `ProductionBatch` schema unchanged. `StockMovementReason` ENUM unchanged. Alembic head remains `012_extend_user_roles`.

**Error codes:** `variant_not_found_or_wrong_product` (422, lists offending ids), `duplicate_variant` (422), `empty_items` (422 — defensive; Pydantic catches the API path), `too_many_items` (422 — defensive), plus the existing `invalid_quantity` / `no_material_requirements` / `insufficient_materials`. Pydantic returns its standard 422 detail array for `min_length=1` / `max_length=50` / `ge=1` violations.

**Frontend.** `frontend/src/app/dashboard/production/CreateBatchModal.tsx` is split into Single ↔ Շարք tabs:

- **Single mode** is unchanged — same fields, same submit, same payload to `POST /production/batches`.
- **Շարք mode** after a product is selected: a per-variant table (checkbox / `Չափս` / `Գույն` / `Մնացորդ` / `Քանակ`), a common-quantity input + `Կիրառել ընտրվածներին` button (writes the common qty into every selected row's qty input — manual override still possible per row), an `Ընտրել ըստ գույնի` helper (pick a color, click `Ընտրել`), a footer counter ("Ընտրված է՝ N տարբերակ · ընդհանուր քանակ՝ M"), and a `Չեղարկել ընտրությունը` link. Submit is disabled while no variants are selected, any selected qty < 1, the count exceeds 50, or a request is in flight. On 2xx the modal closes immediately and toasts `Ստեղծվեց N արտադրություն`.

**Size ordering / "S → XL" helper intentionally not in v1** — sizes are free-form `String(50)` on `ProductVariant`. Adding a canonical-order constant or a `ProductVariant.sort_order` column is parked as a possible follow-up.

**Tests:** 16 new cases in `backend/tests/test_production_batches.py` — happy path, aggregate-shortage rollback, wrong-product variant rolls back, duplicate / empty / oversized / qty=0 rejected, missing material requirements rejected, audit emits one row per created batch, single-create still works, **one `StockMovement` per material** verified via `/inventory/materials/{id}/movements`, RBAC matrix `admin` / `director` / `production_manager` succeed and `warehouse_manager` / `simple_user` 403.

**Live verification (deployed 2026-05-04):**

- `/ready` 200, `/` 200, `/dashboard/production` 200.
- Three smoke probes against `POST /production/batches/bulk` returned the expected 422 with the expected codes (`variant_not_found_or_wrong_product`, Pydantic `min_length`, `value_error duplicate variant_id`) — no batches created during smoke.
- Frontend bundle (`hoso30/art-frontend:v33`) contains the five new Armenian strings (`Մեկական`, `Շարք`, `Ընդհանուր քանակ`, `Կիրառել ընտրվածներին`, `Ընտրել ըստ գույնի`) and the endpoint URL `/production/batches/bulk` baked into compiled chunks.
- Plan summary: `0 to add, 3 to change, 0 to destroy`. No protected-resource changes (PostgreSQL server / database / Storage Account / container / management locks all untouched).
- Manual click-through by the user confirmed the Շարք mode end-to-end.

**Known residual risk — server-side idempotency.** The bulk endpoint has no `Idempotency-Key` support. A network-level retry after a successful POST could create a duplicate set of batches and double-deduct materials. The single-create endpoint has the same risk (pre-existing). Mitigations in place: the frontend disables submit while the request is in flight, closes the modal on 2xx (so the only retry path is "reopen modal + re-confirm"), and the Pydantic 50-item cap bounds blast radius. **Possible follow-up task:** add `Idempotency-Key` request-header support backed by a small `idempotency_keys` table — propose separately if needed.

#### Rollback (bulk v36 / v33 → previous live)

The previous live tags `v35` (backend) / `v32` (frontend) are still in the registry. **No DB rollback needed for this task** — no migration was applied. v36 → v35 is a clean image-tag flip.

1. Edit `terraform/envs/dev/terraform.tfvars`:
   ```
   backend_image_tag  = "v35"
   frontend_image_tag = "v32"
   ```
2. From `terraform/envs/dev/`:
   ```bash
   source .env.terraform
   terraform plan -out=tfplan
   ```
   Expected plan: **0 to add, 3 to change, 0 to destroy** — `azapi_resource.backend_main`, `azapi_resource.backend_worker[0]`, `azurerm_linux_web_app.frontend` revert to v35 / v32. Verify the plan shows **no** changes to the four protected data resources (PostgreSQL server / database, Storage Account / container) or the two `azurerm_management_lock` resources.
3. `terraform apply tfplan` (~40–80 s).
4. Smoke check:
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw frontend_url)/"
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw backend_url)/ready"
   terraform output | grep -E "deployed_image|backend_image"  # → v32 / v35
   ```

**Caveats:**

- The `POST /production/batches/bulk` endpoint disappears on rollback (404 on v35). The v32 frontend doesn't render the Շարք tab, so flipping both tags together is the clean path. Do **not** roll back backend without also rolling back the frontend.
- **Bulk batches already created on v36 stay valid after rollback.** They're regular `ProductionBatch` rows with the existing schema — they appear in the production list, can be completed via the normal `/complete` endpoint, and don't depend on the bulk endpoint to exist.
- **Materials already deducted stay deducted.** No double-deduction risk on rollback (the `StockMovement` ledger is append-only and Inventory is already at the post-deduction state).

## Done (deployed v35 / v32, prior commit)

### RBAC — five user roles with backend authorization matrix

Five roles on `User.role`: `admin`, `director`, `production_manager`, `warehouse_manager`, `simple_user`. **Backend is authoritative** — every API endpoint enforces authorization via `Depends(require_roles(*GROUP))` from `backend/app/dependencies.py`. The frontend's `MODULE_ACCESS` table only hides UI elements the user couldn't use anyway.

**Migration:** `012_extend_user_roles` extends the existing `userrole` Postgres ENUM with the three new values via three idempotent `ALTER TYPE userrole ADD VALUE IF NOT EXISTS …` statements. **Non-destructive**: existing `admin` / `simple_user` rows untouched. Down-revision `011_order_stock_deducted`. Whitelisted in `backend/entrypoint.sh`.

**Rollback caveat:** the ENUM extension is forward-only. Postgres does not support `ALTER TYPE … DROP VALUE`, so a code-rollback to v34 / v31 (or any pre-RBAC backend) is only safe if no `users.role` row holds `director` / `production_manager` / `warehouse_manager`. Live DB currently has user id 7 (`art@art.am`, role `director`) as a smoke-test canary, so any forced rollback today must first run:
```sql
UPDATE users SET role = 'simple_user'
WHERE role IN ('director', 'production_manager', 'warehouse_manager');
```
against the `art_admin` DSN. See `ROLLBACK_NOTES.md` "RBAC ENUM extension is forward-only" and `KNOWN_RISKS.md` #14.

**Per-role expected behaviour (full matrix in `CURRENT_STATE.md` "RBAC matrix — load-bearing"):**

- **admin** — full access. Can manage all roles. Last-active-admin protection (`last_admin_required` 422) prevents demotion or deactivation that would leave zero active admins.
- **director / Տնօրեն** — manages business modules (orders, production, products, inventory, customers, reports, activity). On `/users`, sees / creates / updates **only `simple_user` accounts** (server-filtered via `restrict_to_role=UserRole.simple_user`). Cannot create or promote anyone to `admin` / `director` / `production_manager` / `warehouse_manager` — guard returns 403 `role_assignment_denied`. `GET /users/{id}` for a non-`simple_user` target returns 403 `user_management_denied`.
- **production_manager / Արտադրության ղեկավար** — manages `/orders`, `/production`, `/products`. Read-only on `/inventory/materials`. Allowed reports: `/reports/production`, `/reports/material-consumption`, `/reports/damaged-stock`. Denied: `/users`, `/customers`, sales / dashboard / inventory / low-stock / customer-discounts reports, `/activity-logs`.
- **warehouse_manager / Պահեստապետ** — manages `/inventory` only. All other dashboard modules return 403.
- **simple_user / Օգտատեր** — existing behavior preserved. Lists only own-customer-scoped orders, browses catalog, manages own account.

**Backend code structure:**
- `backend/app/dependencies.py` — role group constants (`ADMIN_ONLY`, `USER_MANAGEMENT`, `BUSINESS_MANAGER`, `INVENTORY_MANAGER`, `PRODUCTION_INVENTORY_READ`, `CUSTOMER_MANAGEMENT`, `REPORT_MANAGEMENT`, `PRODUCTION_REPORTS`, `ACTIVITY_VIEW`, `ORDERS_VIEW`, `PRODUCTS_VIEW`) + `require_roles(*allowed)` factory.
- `backend/app/users/service.py` — `can_assign_role(actor, target_role)`, `can_manage_user(actor, target)`, `count_active_admins(db)`, `is_last_active_admin(db, user)`, and `list_users(..., restrict_to_role=)`.
- `backend/app/users/router.py` — full rewrite: `_restrict_for(actor)`, `_ensure_can_manage`, `_ensure_can_assign_role`, self-role-change / self-deactivation / last-admin guards in PATCH and DELETE.
- `backend/app/users/schemas.py` — `role: UserRole` (Pydantic enum) on `UserCreate` / `UserUpdate` / `UserResponse`. Unknown role strings rejected with 422 before route runs.
- All other routers updated to use the new role groups (`customers`, `orders`, `products`, `production`, `inventory`, `reports`, `activity`).

**Frontend code structure:**
- `frontend/src/lib/permissions.ts` — single source of truth: `MODULE_ACCESS` table, `canAccessModule`, `canAssignRole`, `allowedRolesFor`, `ROLE_LABELS` (`Ադմին` / `Տնօրեն` / `Արտադրության ղեկավար` / `Պահեստապետ` / `Օգտատեր`).
- `frontend/src/lib/auth.ts` — added `requireRoles(...allowed)` and `requireModule(module)` helpers alongside the existing `requireAdmin` / `requireAuth`.
- `frontend/src/types/models.ts` — `UserRole` union type union; `User.role: UserRole`.
- `frontend/src/components/layout/{Sidebar,TopHeader,MobileNav}.tsx` — nav and labels driven by `canAccessModule` / `ROLE_LABELS`.
- All dashboard route guards migrated from binary `requireAdmin()` to `requireModule(...)` / `requireRoles(...)`.
- `frontend/src/app/dashboard/users/{page,UserActions,EditUserForm}.tsx` — role `<Select>` options computed from `allowedRolesFor(actor)`; the role select on the edit form is disabled when `actor.id === user.id` (self-role-change is blocked server-side, but disabling the field surfaces this in the UI with a hint).

**Tests:** `backend/tests/test_authorization_matrix.py` — 51 passed, 2 skipped. Skips are documented unreachable-via-API last-admin scenarios; the underlying guard is exercised directly by `test_is_last_active_admin_service_helper`. Covers: enum membership, Pydantic 422 on unknown role, director's role-creation matrix, director list/get/update isolation, self-role-change & self-deactivation blocked, PM module access matrix (parametrized), WM module access matrix (parametrized), director full module access (parametrized), simple_user behavior preserved, plus direct unit tests on `can_assign_role` / `can_manage_user`.

**Smoke verification (deployed 2026-05-02):**

- Backend `/ready` → HTTP 200; frontend `/` → HTTP 200.
- `POST /api/v1/auth/login` (admin) → 200, `role:"admin"`.
- `GET /api/v1/users?limit=20` → 7 rows; existing admin and simple_user accounts intact.
- Frontend bundle (`hoso30/art-frontend:v32`) contains the three new Armenian labels (`Տնօրեն`, `Արտադրության ղեկավար`, `Պահեստապետ`) in compiled chunks.
- Migration 012 applied: DB now contains `users.role='director'` (id 7), only possible if the `userrole` ENUM was extended.
- Plan summary on apply: `0 to add, 3 to change, 0 to destroy`. No protected-resource changes (PostgreSQL server / database / Storage Account / container / management locks all untouched).

#### Rollback (RBAC v35 / v32 → previous live)

The previous live tags `v34` (backend) / `v31` (frontend) are still in the registry. **The DB-side prep is mandatory if any non-original-role user exists.**

1. **DB preparation (mandatory if non-original-role users exist).** Connect via the `art_admin` DSN and demote the canary (and any other manager-tier rows) back to `simple_user`:
   ```sql
   UPDATE users SET role = 'simple_user'
   WHERE role IN ('director', 'production_manager', 'warehouse_manager');
   ```
   Verify: `SELECT id, email, role FROM users ORDER BY id;` should show only `admin` / `simple_user`.
2. Edit `terraform/envs/dev/terraform.tfvars`:
   ```
   backend_image_tag  = "v34"
   frontend_image_tag = "v31"
   ```
3. From `terraform/envs/dev/`:
   ```bash
   source .env.terraform
   terraform plan -out=tfplan
   ```
   Expected plan: **0 to add, 3 to change, 0 to destroy** — `azapi_resource.backend_main`, `azapi_resource.backend_worker[0]`, `azurerm_linux_web_app.frontend` revert to v34 / v31. Verify the plan shows **no** changes to the four protected data resources or the two `azurerm_management_lock` resources.
4. `terraform apply tfplan` (~40–80 s).
5. Smoke check:
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw frontend_url)/"
   curl -sS -o /dev/null -w "%{http_code}\n" "$(terraform output -raw backend_url)/ready"
   terraform output | grep -E "deployed_image|backend_image"  # → v31 / v34
   ```

**No DB migration rollback.** The ENUM extension is forward-only — `012_extend_user_roles.downgrade()` is a documented no-op. The rollback strategy is to leave the ENUM extended and demote any rows that use the new values, not to remove the values from the type.

## Done (deployed v34 / v31, prior commit)

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

Live: `art-frontend:v33`, `art-backend:v36`. Blacklisted in `terraform/envs/dev/variables.tf` validation:

| Tag | Reason retired |
|---|---|
| `art-backend:v13` | Failed migration `009`; the boot guard exists to recover from it. See `KNOWN_RISKS.md` #2. |
| `art-backend:v26` | Task B regression: slowapi `headers_enabled=True` + dict-return endpoints raised inside `_inject_headers`, short-circuiting the rate limiter. |
| `art-backend:v27` | Task B regression: missing XFF port-strip; Azure App Service prepends ephemeral source ports to each XFF entry, so every request landed in a fresh rate-limit bucket and the limit never fired. |
| `art-frontend:v21` | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed in Azure with `Module parse failed: Unexpected character '@'` on Tailwind globals.css under `NODE_ENV=production`. Always use `frontend/Dockerfile.azure` for production builds. |
| `art-frontend:v22` and `v23` | Built from Git Bash on Windows without `MSYS_NO_PATHCONV=1`; MSYS rewrote `--build-arg NEXT_PUBLIC_API_URL=/api/v1` to `C:/Program Files/Git/api/v1`, which webpack inlined into every `clientFetch` call. Every browser-side fetch threw `TypeError: Failed to fetch`. SSR was unaffected. v22 was the symptomless variant; v23 surfaced the bug because its modal's defensive logic exposed it. See `KNOWN_RISKS.md` #8. |

Backend tag lineage (live progression):
- `v21` → `v25` (Task A) → `v28` (Task B) → `v29` (Task C1) → `v30` (Task C2a/b) → `v31` (orders dropdown UX) → `v32` (partial production batches) → `v33` (sales per-customer) → `v34` (sales per-order) → `v35` (RBAC five roles, migration `012_extend_user_roles`) → **`v36` (bulk production batch creation, no migration) — current**.
- v25, v28, v29, v30, v31, v32, v33, v34, v35 are retired but not blacklisted. Rolling back to a pre-v35 tag is conditional — see "RBAC ENUM extension is forward-only" in `KNOWN_RISKS.md` #14 and `ROLLBACK_NOTES.md`. Rolling back v36 → v35 is unconditional (no migration was applied for the bulk task; `POST /production/batches/bulk` simply disappears).

Frontend tag lineage (live progression):
- `v24` (post-MSYS-fix baseline) → `v25`–`v27` (orders UX) → `v28` (production page) → `v29` (per-customer reports) → `v30` (limit fix) → `v31` (per-order reports) → `v32` (RBAC permissions, sidebar/route/user-form gating) → **`v33` (bulk production modal — Single ↔ Շարք toggle) — current**.

When publishing a new frontend tag from Git Bash on Windows, **always** set `MSYS_NO_PATHCONV=1` and verify the bundle is clean before pushing — see CLAUDE.md "Building Docker images on Windows / Git Bash" for the verification command.

## Possible follow-ups (not started)

### Server-side `Idempotency-Key` for production batch creation
The single-create and bulk-create endpoints both lack idempotency. A network-level retry after a successful POST would create duplicate batches and double-deduct materials. The current frontend mitigation (disable submit while in flight, close modal on 2xx, reopen-and-reconfirm to retry) is good enough for typical usage but not race-proof.

A clean implementation would add `Idempotency-Key` request-header support, backed by a small `idempotency_keys(key, user_id, request_hash, response_blob, created_at)` table. Replay returns the original response without touching `Inventory`. Affects both single and bulk endpoints; covers more than this task. Propose separately if the duplicate-on-retry risk becomes load-bearing.

### Variant `sort_order` for bulk size selection
`ProductVariant.size` is free-form `String(50)`; the bulk modal therefore intentionally does **not** offer an "S → XL" range helper because we cannot assume a canonical order. If the client wants robust ordering across non-standard sizes, options:
- Add `ProductVariant.sort_order INT NOT NULL DEFAULT 0` (Alembic migration, default 0 is safe for existing data) and sort the variants table by `(sort_order, size)`.
- Or maintain a hard-coded canonical-order constant on the frontend and use it only when every displayed size matches an entry; otherwise hide the range helper.

Both are forward-compatible with the current bulk endpoint — no API change.

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
