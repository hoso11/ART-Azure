# Admin Override / Force Delete Model

State of every deletable entity in the system, the normal-delete refusal codes, the admin Force Delete escape, and the preservation guarantees.

**Deployed:** backend `v48`, frontend `v46`.
**Origin policy:** every admin-facing delete refusal must have a typed `FORCE DELETE` escape. No admin workflow ends with a generic "Cannot delete because referenced" without a path forward. UI shows reference counts inline before the click; modal lists exactly what will be deleted and what will be preserved.
**Universal preservation rules:**
- Audit logs are **never deleted** under any path.
- Stock movements, order history, production-batch counters, and reporting data are preserved via FK→NULL + per-row snapshot columns.
- Sellable / damaged stock counters are **never auto-reversed** by a force-delete — the modal warns; admin can manually adjust inventory afterward.

---

## Entity matrix

| Entity | Normal delete | Force delete | Preserves |
|---|---|---|---|
| Material | Hard-delete, **typed 409 `material_in_use`** if referenced (recipes / stock movements) | `DELETE /api/v1/inventory/materials/{id}/force` — gated on `inventory.quantity_on_hand == 0` only. Snapshot pattern: `stock_movements.material_id` → NULL + `material_name_snapshot` populated; `product_materials` + `product_size_material_requirements` rows cascade-removed. | Stock-movement ledger, material-consumption report (renders `{name} (ջնջված)` for orphan rows), audit logs. |
| Product | **Soft-delete** (`is_active = False`). Never refuses. | `DELETE /api/v1/products/{id}/force` — gated on **zero variants AND zero production batches** (chain through Variant force-delete first if needed). ORM cascade clears `product_images`, `product_materials`, `product_size_material_requirements`; image blob keys returned to the router for best-effort cleanup. | Audit logs, blob storage at admin discretion. |
| Variant | Hard-delete, typed 409 `variant_has_orders` (when `order_items > 0`), `variant_has_production_batches` (when `production_batches > 0`), `variant_in_use` (defensive catch-all). Reference counts surface in the typed Armenian detail string. | `DELETE /api/v1/products/variants/{id}/force` — **no business gate, admin only**. Snapshot pattern: every referring `order_items` row gets `variant_name_snapshot = "<size> / <color>"` + `product_name_snapshot = <product.name>`, FK → NULL; same on every referring `production_batches` row; variant row hard-deleted. | Order history (`quantity`, `unit_price`, `fulfilled_from_stock`, `production_quantity` untouched), production batch counters + stage progression + linked stock movements, audit logs. Sales report renders `{product} (ջնջված)` for orphan order items. |
| Production Batch | Hard-delete with **atomic stock rollback** when `stage_status == "completed" AND stock_added`. Refuses with `batch_not_completed` (422) / `batch_rollback_would_underflow` (422) / `batch_legacy_no_movement_link` (422) otherwise. | `DELETE /api/v1/production/batches/{id}/force` — **no business gate, universal admin escape**. Works in `pending` / `in_progress` / `completed`, with or without linked stock movements. Explicit `UPDATE stock_movements SET batch_id = NULL` before delete (SQLite-portable, Postgres-idempotent — Postgres FK `ON DELETE SET NULL` would also handle it, but the explicit update keeps behavior identical across both backends). Inventory + variant counters NOT touched. | Stock-movement ledger (every row survives with `batch_id = NULL` so consumption is still attributable to the material), variant `stock_quantity` + `damaged_stock_quantity` at their current values, audit logs. Modal warns the admin that material/stock counters are NOT rolled back. |
| Order | Hard-delete, typed 422 `order_stock_already_deducted` (when `stock_deducted = True`) / `order_has_active_production` (when any `ProductionStage.status != "pending"`). Removes `order_items` + pending `production_stages` + `production_logs` via per-row ORM delete on success. | `DELETE /api/v1/orders/{id}/force` — **no business gate, admin only**. Hard-deletes the order even with stock deducted / active production. Audit log row written before the deletion. | Audit logs. Stock movements that reference this order via `order_id` survive with `order_id = NULL` (Pre-existing FK behavior, predates v47). |
| Category | **v48**: Hard-delete, typed 409 `category_has_products` (with product count in the Armenian detail string). Was previously a bare `db.delete()` → 500 `IntegrityError`. | `DELETE /api/v1/categories/{id}/force` — **no business gate, admin only**. `UPDATE products SET category_id = NULL WHERE category_id = X`, then `DELETE FROM categories WHERE id = X`. `Product.category_id` was already nullable in the original schema — **no migration needed**. | Every product survives with its own name, SKU, variants, images, recipes, orders, and production history. Products become "uncategorized" in the UI until reassigned. Audit logs. |

---

## Entities that cannot be force-deleted (and don't need to be)

| Entity | Reason | Status |
|---|---|---|
| `ProductImage` | Leaf — no FK referrers; bare `DELETE /api/v1/products/images/{id}` always succeeds. | OK |
| `ProductMaterial` (recipe header) | Leaf — bare `DELETE /api/v1/products/materials/{pm_id}` always succeeds. | OK |
| `ProductSizeMaterialRequirement` (per-size recipe row) | Leaf — bare `DELETE /api/v1/products/{pid}/size-requirements/{req_id}` always succeeds. | OK |
| `OrderItem` (within an order) | Leaf — nothing FKs to OrderItem. Its own FKs are all nullable since v47. | OK |
| Customer | Soft-delete only (`is_active = False`); never refuses. Out of scope per CLAUDE.md "No Customer/User force-delete". | OK |
| User | Soft-delete only (`is_active = False`). Only blocker is the **last-active-admin guard** (`last_admin_required` 422) — by design, resolved by promoting another user to admin first. | OK |
| `ProductionStage` / `ProductionLog` | No DELETE endpoint at all. Stages cascade with the parent order. Logs cascade with the stage. | OK (feature gap, not a dead end) |
| `StockMovement` | No DELETE endpoint — ledger preservation by design. | OK |
| `ActivityLog` | No DELETE endpoint. **Hard rule.** | OK |
| `Inventory` (1:1 with Material) | No DELETE endpoint. Cascades with the parent Material. | OK |

---

## Migrations involved

| Revision | Purpose | Forward-only? |
|---|---|---|
| `013_stock_movement_batch_id` | `stock_movements.batch_id` nullable + FK `ON DELETE SET NULL` to `production_batches`. Underpins Production Batch normal delete (safe rollback) and the v47 force-delete that orphans linked movements. | No — downgrade restores the column to NOT NULL; will fail if any row has been NULLed by a batch delete. |
| `014_stock_movement_mat_null` | `stock_movements.material_id` nullable + `material_name_snapshot VARCHAR(255)`. Underpins Material force-delete. | **Yes** — `downgrade()` can run only if no force-delete has occurred. Same caveat as `012_extend_user_roles`. |
| `015_variant_force_delete` | `order_items.product_variant_id` + `production_batches.variant_id` nullable, plus `variant_name_snapshot` + `product_name_snapshot` on both tables. Underpins Variant force-delete. | **Yes** — `downgrade()` fails if any orphan rows exist. |

No migration was needed for Product / Order / Category force-delete (those use either soft-delete + cascade, ORM-only changes, or pre-existing nullable FKs).

---

## Activity log integration

Every force-delete writes a row with action `<entity>.force_deleted`:

| Action | Module | Audit `details` summary |
|---|---|---|
| `inventory.material_force_deleted` | inventory | "Force deleted material with zero stock. Cascaded N product-material and M size-requirement row(s). Preserved K ledger row(s) as orphans." |
| `product.force_deleted` | product | "Force deleted product (zero variants). Cascade-removed N image(s), M material recipe row(s), K size requirement(s)." |
| `variant.force_deleted` | variant | "Force deleted variant {product_name} / {variant_name}. Snapshotted N order item(s) and M production batch(es); stock_movements ledger preserved." |
| `production.batch_force_deleted` | production_batch | "Force deleted production batch (stage_status=X, materials_deducted=Y). Orphaned N stock_movement(s) via batch_id=NULL." |
| `order.force_deleted` | order | (existing pre-v47 details string) |
| `category.force_deleted` | category | "Force deleted category 'X'. Cleared category_id on N product(s); products remain intact and become uncategorized." |

Activity log UI styling: every `*.force_deleted` row gets a red row tint + an **Ուժով** red badge. The styling is **data-driven by the action suffix** (`log.action.endsWith(".force_deleted")` in `frontend/src/app/dashboard/activity/page.tsx`), so any future force-delete entity inherits the visual treatment automatically.

---

## UI contract

Every force-delete button follows the same pattern (see `ForceDeleteMaterialButton`, `ForceDeleteProductButton`, `ForceDeleteVariantButton`, `ForceDeleteBatchButton`, `ForceDeleteOrderButton`, `ForceDeleteCategoryButton`):

1. Visible only when actor is admin (`session.role === "admin"`).
2. Red text + tooltip in the list/detail action area.
3. Click opens a modal with a red border, a `!` red badge, and an Armenian title.
4. Modal body lists:
   - **What will be deleted** — the entity row, cascade-removed metadata.
   - **What will be preserved** — snapshot columns, ledger rows, downstream entities (with the snapshot label e.g. "կպահպանվի, բայց … կնշվի որպես ջնջված").
   - **What will NOT be auto-reversed** — sellable/damaged stock, materials, variant counters.
   - **Reference counts inline** — e.g. "Կապված է N պատվերի հետ, M արտադրության հետ".
   - **Irreversibility warning** — "Գործողությունը անդարձելի է".
5. A monospace input field requiring exactly `FORCE DELETE` to enable the red Confirm button.
6. Success toast in Armenian, then `router.refresh()` to re-fetch the SSR page so counts and lists update.

---

## What was previously a dead end (closed in v48)

- **Category delete with referencing products** — before v48 returned an untyped 500 `IntegrityError` (Postgres FK `NO ACTION` default with `Product.category_id` referencing the category). Admin had no escape. v48 added the typed 409 + the `/force` escape.

---

## What is intentionally NOT in this framework

- **Order force-delete cascade into production stages** — order force-delete handles its own production-stage cleanup; not a new force-delete entity.
- **Customer / User force-delete** — soft-delete only, by design.
- **ProductionStage admin delete** — no current dead end (no DELETE endpoint exists); flagged as a feature gap in the v47 audit, not in scope for v48.
- **`category_name_snapshot` on `Product`** — optional polish; products already carry their own name/SKU/variants, and the category-force-delete audit log captures the destroyed category name.

---

## Reference

- Backend service code: `app.products.service.force_delete_variant`, `app.production.service.force_delete_production_batch`, `app.inventory.service.force_delete_material`, `app.products.service.force_delete_product`, `app.products.service.force_delete_category`, `app.orders.service.force_delete_order`.
- Frontend components: `frontend/src/app/dashboard/{inventory,products,production,orders}/ForceDelete*Button.tsx`, `frontend/src/app/dashboard/products/CategoryManager.tsx`.
- Test coverage: `backend/tests/test_inventory.py` (material), `backend/tests/test_products.py` (variant + product + category — 6 new variant tests + 7 new category tests added in v47 and v48), `backend/tests/test_production_batches.py` (batch — inverted two tests in v47 to remove the legacy-completed-only gate).
- Related: `CURRENT_STATE.md` "Admin Override / Force Delete framework", `KNOWN_RISKS.md` #16 (firewall-rule lock conflict), #17 (MinIO local test infra).
