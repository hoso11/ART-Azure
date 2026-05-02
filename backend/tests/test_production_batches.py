"""
Stock-based production batch tests (production-for-stock).

Each call to /complete is a DELTA, not a final total. Cumulative counters
live on the batch row; the batch flips to stage_status='completed' /
stock_added=True only when cumulative good + damaged == quantity_to_produce.

Cases:
  1.  Enough materials                  → batch created (201), materials deducted
  2.  Not enough materials              → 422, materials unchanged
  3.  Single delta == quantity          → all-good completes the batch in one shot
  4.  Terminal idempotency              → call after stock_added=True is no-op
  5.  Missing material requirements     → 422 with code="no_material_requirements"
  6.  Order-based production            → skipped (3-status flow, see migration 011)
  7.  Single delta good+damaged         → split sum equals quantity completes batch
  8.  All damaged in one delta          → damaged += quantity, sellable unchanged
  9.  Partial delta accepted            → cumulative updates, status stays in_progress
 10.  Negative good_quantity            → 422 with code="invalid_quantities"
 11.  Negative damaged_quantity         → 422 with code="invalid_quantities"
 12.  Partial save keeps materials      → materials stay deducted across deltas
 13.  Audit log split                   → progress rows for partials, one completed row
 14.  Multiple partials reach completion → cumulative stock movement matches deltas
 15.  Delta exceeds remaining           → 422 delta_exceeds_remaining, no movement
 16.  Empty delta (0+0)                 → 422 empty_delta, no movement
 17.  Partial save promotes pending     → first delta on pending → in_progress
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── helpers ─────────────────────────────────────────────────────────────────

async def _make_product(client, admin_cookies, *, sku, size, color, stock_quantity=0, price=10.00):
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"PB-{sku}",
            "sku": sku,
            "variants": [
                {"size": size, "color": color, "price": price, "stock_quantity": stock_quantity},
            ],
        },
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["id"], body["variants"][0]["id"]


async def _make_material(client, admin_cookies, *, sku, qty):
    resp = await client.post(
        "/api/v1/inventory/materials",
        json={"name": f"PB-Mat-{sku}", "sku": sku, "unit": "meters", "quantity_on_hand": qty},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _add_size_requirement(client, admin_cookies, *, product_id, material_id, size, qty_per_item):
    resp = await client.post(
        f"/api/v1/products/{product_id}/size-requirements",
        json={"material_id": material_id, "size": size, "quantity_per_item": qty_per_item},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text


async def _create_batch(client, admin_cookies, *, product_id, variant_id, quantity):
    return await client.post(
        "/api/v1/production/batches",
        json={
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity_to_produce": quantity,
        },
        cookies=admin_cookies,
    )


async def _variant_stock(client, admin_cookies, product_id, variant_id) -> int:
    resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    for v in resp.json()["variants"]:
        if v["id"] == variant_id:
            return int(v["stock_quantity"])
    raise AssertionError(f"variant {variant_id} not found in product {product_id}")


async def _variant_damaged_stock(client, admin_cookies, product_id, variant_id) -> int:
    resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    for v in resp.json()["variants"]:
        if v["id"] == variant_id:
            return int(v.get("damaged_stock_quantity", 0))
    raise AssertionError(f"variant {variant_id} not found in product {product_id}")


async def _complete_batch(client, admin_cookies, batch_id, *, good, damaged, reason=None):
    body = {"good_quantity": good, "damaged_quantity": damaged}
    if reason is not None:
        body["defect_reason"] = reason
    return await client.patch(
        f"/api/v1/production/batches/{batch_id}/complete",
        json=body,
        cookies=admin_cookies,
    )


async def _material_qty(client, admin_cookies, material_id) -> Decimal:
    resp = await client.get(f"/api/v1/inventory/materials/{material_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    inv = resp.json().get("inventory")
    return Decimal(str(inv["quantity_on_hand"])) if inv else Decimal("0")


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enough_materials_creates_batch_and_deducts(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 1: 100 meters on hand, batch of 10 needs 10*2=20 → batch created, material 100 → 80."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-OK-001", size="M", color="Black", stock_quantity=0
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-OK-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2
    )

    resp = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=10
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["materials_deducted"] is True
    assert body["stock_added"] is False
    assert body["current_stage"] == "cutting"
    assert body["stage_status"] == "pending"
    assert body["production_type"] == "stock_based"
    assert body["quantity_to_produce"] == 10

    # Material deducted: 100 - (10 * 2) = 80
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("80")
    # Variant stock unchanged at creation — only added on completion
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0


@pytest.mark.asyncio
async def test_not_enough_materials_fails_and_changes_nothing(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 2: only 5 meters on hand, batch of 10 needs 20 → 422, material stays at 5, no batch."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-SHORT-001", size="M", color="Yellow", stock_quantity=0
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-SHORT-001", qty=5)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2
    )

    resp = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=10
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "insufficient_materials"

    # Nothing deducted
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("5")
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0

    # No batches exist
    list_resp = await client.get("/api/v1/production/batches", cookies=admin_cookies)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_complete_all_good_increases_sellable_stock_only(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 3: batch of 7, completed as 7 good + 0 damaged → sellable += 7,
    damaged counter unchanged at 0."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-CMP-001", size="L", color="Blue", stock_quantity=0
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-CMP-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="L", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    batch_id = create.json()["id"]

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == 0

    complete = await _complete_batch(client, admin_cookies, batch_id, good=7, damaged=0)
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["stage_status"] == "completed"
    assert body["stock_added"] is True
    assert body["good_quantity"] == 7
    assert body["damaged_quantity"] == 0
    assert body["defect_reason"] is None
    assert body["completed_at"] is not None

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 7
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == 0


@pytest.mark.asyncio
async def test_terminal_idempotency_after_completion(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 4: once cumulative reaches quantity_to_produce and stock_added=True,
    any further /complete call is a silent no-op — neither sellable nor damaged
    stock moves a second time and the cumulative split stays as recorded."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-DBL-001", size="S", color="Pink", stock_quantity=2
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DBL-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="S", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=5
    )
    batch_id = create.json()["id"]

    # First delta fills the batch in one shot (3 + 2 = 5 = quantity).
    first = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=2, reason="QC tears")
    assert first.status_code == 200, first.text
    assert first.json()["stock_added"] is True
    sellable_after_first = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_after_first = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)
    assert sellable_after_first == 2 + 3  # initial 2 + 3 good delta
    assert damaged_after_first == 2

    # Second call after stock_added=True — silent no-op even with non-zero deltas.
    second = await _complete_batch(client, admin_cookies, batch_id, good=1, damaged=0)
    assert second.status_code == 200
    body = second.json()
    assert body["stock_added"] is True
    assert body["good_quantity"] == 3
    assert body["damaged_quantity"] == 2

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_after_first
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_after_first


@pytest.mark.asyncio
async def test_missing_material_requirements_returns_clear_error(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 5: variant exists, materials exist, but no ProductSizeMaterialRequirement
    rows are defined for that product+size → batch creation fails with code=no_material_requirements."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-NOREQ-001", size="XL", color="Red"
    )
    # Note: NO call to _add_size_requirement — that's the whole point.

    resp = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=3
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "no_material_requirements"
    assert body.get("detail") == "Տվյալ ապրանքը արտադրելու համար համապատասխան նյութեր սահմանված չեն։"


@pytest.mark.asyncio
async def test_partial_complete_increments_both_counters(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 7: batch of 7 → 5 good + 2 damaged. sellable += 5, damaged += 2."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-PRT-001", size="M", color="Black", stock_quantity=3
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-PRT-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    batch_id = create.json()["id"]

    sellable_before = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_before = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)
    assert sellable_before == 3
    assert damaged_before == 0

    complete = await _complete_batch(
        client, admin_cookies, batch_id, good=5, damaged=2, reason="2 units with stitching defects",
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["good_quantity"] == 5
    assert body["damaged_quantity"] == 2
    assert body["defect_reason"] == "2 units with stitching defects"
    assert body["stock_added"] is True

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_before + 5
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_before + 2


@pytest.mark.asyncio
async def test_complete_all_damaged_does_not_increase_sellable_stock(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 8: 0 good + 7 damaged → sellable unchanged, damaged += 7. Materials stay deducted."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-DMG-001", size="L", color="Green", stock_quantity=4
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DMG-001", qty=50)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="L", qty_per_item=3
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=4
    )
    batch_id = create.json()["id"]

    # 50 - (4*3) = 38 deducted on creation.
    qty_after_create = await _material_qty(client, admin_cookies, material_id)
    assert qty_after_create == Decimal("38")

    sellable_before = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_before = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)

    complete = await _complete_batch(
        client, admin_cookies, batch_id, good=0, damaged=4, reason="Wrong color run",
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["good_quantity"] == 0
    assert body["damaged_quantity"] == 4
    assert body["materials_deducted"] is True
    assert body["stock_added"] is True  # completion processed; not "stock added to sellable"

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_before
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_before + 4

    # Material is NOT given back. 38 stays at 38.
    qty_after_complete = await _material_qty(client, admin_cookies, material_id)
    assert qty_after_complete == qty_after_create


@pytest.mark.asyncio
async def test_partial_progress_accepted_stays_in_progress(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 9: a partial delta (cumulative < quantity) is accepted, batch
    stays in_progress / stock_added=False. Variant counters move by the delta."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-PRG-001", size="M", color="Yellow", stock_quantity=1
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-PRG-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    batch_id = create.json()["id"]

    sellable_before = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_before = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)

    # 3 + 2 = 5 < 7 → accepted, batch stays in_progress.
    resp = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=2, reason="QC")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["good_quantity"] == 3
    assert body["damaged_quantity"] == 2
    assert body["stage_status"] == "in_progress"
    assert body["stock_added"] is False
    assert body["completed_at"] is None

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_before + 3
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_before + 2


@pytest.mark.asyncio
async def test_delta_exceeds_remaining_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 15: a delta whose sum would push cumulative past quantity_to_produce
    is rejected with code=delta_exceeds_remaining. No counter moves."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-OVR-001", size="M", color="Yellow"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-OVR-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    batch_id = create.json()["id"]

    # First, a clean partial that uses 4 of the 7.
    first = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=1)
    assert first.status_code == 200
    sellable_after_first = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_after_first = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)

    # Remaining is now 3. Attempt to add 4 more → must reject.
    over = await _complete_batch(client, admin_cookies, batch_id, good=2, damaged=2)
    assert over.status_code == 422
    assert over.json().get("code") == "delta_exceeds_remaining"

    # Direct overshoot from a clean batch (10 > 7) on a fresh batch.
    fresh_create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    fresh_id = fresh_create.json()["id"]
    direct = await _complete_batch(client, admin_cookies, fresh_id, good=5, damaged=5)
    assert direct.status_code == 422
    assert direct.json().get("code") == "delta_exceeds_remaining"

    # Counters from the rejected attempts must be unchanged.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_after_first
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_after_first


@pytest.mark.asyncio
async def test_empty_delta_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 16: good=0 and damaged=0 → 422 with code=empty_delta. No movement."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-EMP-001", size="M", color="Lavender"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-EMP-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=4
    )
    batch_id = create.json()["id"]

    sellable_before = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_before = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)

    resp = await _complete_batch(client, admin_cookies, batch_id, good=0, damaged=0)
    assert resp.status_code == 422
    assert resp.json().get("code") == "empty_delta"

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_before
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_before


@pytest.mark.asyncio
async def test_multiple_partials_reach_completion(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 14: several partial deltas sum to quantity_to_produce. After the
    delta that fills the batch, stage_status='completed' and stock_added=True.
    Variant stock movement equals the cumulative deltas — no extra, no missing."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-MUL-001", size="L", color="Kanach", stock_quantity=2
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-MUL-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="L", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=10
    )
    batch_id = create.json()["id"]

    # Partial 1: +5 good, +0 damaged. Cumulative 5/0, remaining 5, in_progress.
    r1 = await _complete_batch(client, admin_cookies, batch_id, good=5, damaged=0)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["good_quantity"] == 5
    assert b1["damaged_quantity"] == 0
    assert b1["stage_status"] == "in_progress"
    assert b1["stock_added"] is False
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 2 + 5
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == 0

    # Partial 2: +3 good, +1 damaged. Cumulative 8/1, remaining 1, still in_progress.
    r2 = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=1, reason="seam slip")
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["good_quantity"] == 8
    assert b2["damaged_quantity"] == 1
    assert b2["stage_status"] == "in_progress"
    assert b2["stock_added"] is False
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 2 + 5 + 3
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == 1

    # Partial 3: +1 good, +0 damaged. Cumulative 9/1 = 10 = quantity → completed.
    r3 = await _complete_batch(client, admin_cookies, batch_id, good=1, damaged=0)
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["good_quantity"] == 9
    assert b3["damaged_quantity"] == 1
    assert b3["stage_status"] == "completed"
    assert b3["stock_added"] is True
    assert b3["current_stage"] == "ready_for_shipment"
    assert b3["completed_at"] is not None
    # Final stock movement: +9 sellable, +1 damaged across the three deltas.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 2 + 9
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == 1


@pytest.mark.asyncio
async def test_partial_save_promotes_pending_to_in_progress(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 17: a fresh batch starts at stage_status='pending'. The first
    non-final partial delta auto-promotes it to 'in_progress' without needing
    a separate PATCH /production/batches/{id} call."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-PND-001", size="M", color="Cream"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-PND-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=6
    )
    batch_id = create.json()["id"]
    assert create.json()["stage_status"] == "pending"

    resp = await _complete_batch(client, admin_cookies, batch_id, good=2, damaged=0)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stage_status"] == "in_progress"
    assert body["stock_added"] is False
    assert body["good_quantity"] == 2


@pytest.mark.asyncio
async def test_negative_good_quantity_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 10: good_quantity < 0 → 422 with code=invalid_quantities."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-NEG-001", size="S", color="Cyan"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-NEG-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="S", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=4
    )
    batch_id = create.json()["id"]

    resp = await _complete_batch(client, admin_cookies, batch_id, good=-1, damaged=5)
    assert resp.status_code == 422
    assert resp.json().get("code") == "invalid_quantities"


@pytest.mark.asyncio
async def test_negative_damaged_quantity_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 11: damaged_quantity < 0 → 422 with code=invalid_quantities."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-NEG-002", size="S", color="Magenta"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-NEG-002", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="S", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=4
    )
    batch_id = create.json()["id"]

    resp = await _complete_batch(client, admin_cookies, batch_id, good=5, damaged=-1)
    assert resp.status_code == 422
    assert resp.json().get("code") == "invalid_quantities"


@pytest.mark.asyncio
async def test_partial_complete_keeps_materials_deducted(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 12: a partial completion (mix of good + damaged) does not refund
    raw materials — they were consumed regardless of outcome (rule 10)."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-MAT-001", size="M", color="Slate"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-MAT-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=4
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=5
    )
    batch_id = create.json()["id"]

    # 100 - (5*4) = 80 after creation.
    qty_after_create = await _material_qty(client, admin_cookies, material_id)
    assert qty_after_create == Decimal("80")

    complete = await _complete_batch(client, admin_cookies, batch_id, good=4, damaged=1)
    assert complete.status_code == 200

    qty_after_complete = await _material_qty(client, admin_cookies, material_id)
    assert qty_after_complete == qty_after_create


@pytest.mark.asyncio
async def test_complete_with_damage_emits_single_audit_log(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 13: a real /complete writes exactly one production.batch_completed
    audit row, with the breakdown in details. A second idempotent /complete
    does NOT add a second row."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-AUD-001", size="M", color="Olive"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-AUD-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=3
    )
    batch_id = create.json()["id"]

    first = await _complete_batch(
        client, admin_cookies, batch_id, good=2, damaged=1, reason="QC found one tear",
    )
    assert first.status_code == 200

    logs1 = await client.get(
        "/api/v1/activity-logs?action=production.batch_completed&limit=100",
        cookies=admin_cookies,
    )
    matches1 = [
        r for r in logs1.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]
    assert len(matches1) == 1
    details = matches1[0].get("details") or ""
    assert "+2 good" in details
    assert "+1 Խոտան" in details
    assert "QC found one tear" in details

    # Idempotent second call must not duplicate the audit row.
    second = await _complete_batch(client, admin_cookies, batch_id, good=2, damaged=1)
    assert second.status_code == 200

    logs2 = await client.get(
        "/api/v1/activity-logs?action=production.batch_completed&limit=100",
        cookies=admin_cookies,
    )
    matches2 = [
        r for r in logs2.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]
    assert len(matches2) == 1, "second /complete must not emit a duplicate audit row"


@pytest.mark.asyncio
async def test_partial_saves_emit_progress_then_completed_audit_logs(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 13b: across multiple partials, intermediate saves emit
    `production.batch_progress` audit rows; the delta that fills the batch
    emits exactly one `production.batch_completed`. A subsequent no-op call
    after stock_added=True writes no further audit row."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-AUD2-001", size="M", color="Slate"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-AUD2-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=5
    )
    batch_id = create.json()["id"]

    # Two non-final partials, then a completing delta.
    p1 = await _complete_batch(client, admin_cookies, batch_id, good=2, damaged=0)
    assert p1.status_code == 200
    p2 = await _complete_batch(client, admin_cookies, batch_id, good=1, damaged=1, reason="loose seam")
    assert p2.status_code == 200
    p3 = await _complete_batch(client, admin_cookies, batch_id, good=1, damaged=0)
    assert p3.status_code == 200
    assert p3.json()["stock_added"] is True

    progress_logs = await client.get(
        "/api/v1/activity-logs?action=production.batch_progress&limit=100",
        cookies=admin_cookies,
    )
    progress_rows = [
        r for r in progress_logs.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]
    assert len(progress_rows) == 2

    completed_logs = await client.get(
        "/api/v1/activity-logs?action=production.batch_completed&limit=100",
        cookies=admin_cookies,
    )
    completed_rows = [
        r for r in completed_logs.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]
    assert len(completed_rows) == 1

    # Idempotent terminal call must not write any new audit row.
    after = await _complete_batch(client, admin_cookies, batch_id, good=1, damaged=0)
    assert after.status_code == 200
    progress_logs2 = await client.get(
        "/api/v1/activity-logs?action=production.batch_progress&limit=100",
        cookies=admin_cookies,
    )
    completed_logs2 = await client.get(
        "/api/v1/activity-logs?action=production.batch_completed&limit=100",
        cookies=admin_cookies,
    )
    assert len([
        r for r in progress_logs2.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]) == 2
    assert len([
        r for r in completed_logs2.json()["items"]
        if r["entity_type"] == "production_batch" and r["entity_id"] == batch_id
    ]) == 1


@pytest.mark.skip(
    reason=(
        "Order-based production removed in favor of 3-status order flow "
        "(migration 011). The in_production transition is no longer a valid "
        "target. Stock-based ProductionBatch flow (the rest of this file) "
        "is unaffected and remains active."
    )
)
@pytest.mark.asyncio
async def test_order_based_production_still_works(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 6: order-based stage flow is unaffected. Confirm + transition to in_production."""
    prod_resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Order Smoke",
            "sku": "ORD-SMK-001",
            "variants": [{"size": "S", "color": "White", "price": 30.00}],
        },
        cookies=admin_cookies,
    )
    product_id = prod_resp.json()["id"]
    variant_id = prod_resp.json()["variants"][0]["id"]

    mat_resp = await client.post(
        "/api/v1/inventory/materials",
        json={"name": "Order Fabric", "sku": "MAT-ORD-001", "unit": "meters", "quantity_on_hand": 100},
        cookies=admin_cookies,
    )
    material_id = mat_resp.json()["id"]
    await client.post(
        f"/api/v1/products/{product_id}/size-requirements",
        json={"material_id": material_id, "size": "S", "quantity_per_item": 2},
        cookies=admin_cookies,
    )

    order_resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer.id,
            "items": [{"product_variant_id": variant_id, "quantity": 5, "unit_price": 30.00}],
        },
        cookies=admin_cookies,
    )
    order_id = order_resp.json()["id"]

    # draft → confirmed deducts materials via the order flow (5 * 2 = 10)
    r = await client.patch(
        f"/api/v1/orders/{order_id}", json={"status": "confirmed"}, cookies=admin_cookies
    )
    assert r.status_code == 200, r.text

    # confirmed → in_production seeds the initial production stage
    r = await client.patch(
        f"/api/v1/orders/{order_id}", json={"status": "in_production"}, cookies=admin_cookies
    )
    assert r.status_code == 200, r.text

    # The order-based stages list should now include this order
    stages = await client.get(
        "/api/v1/production?page=1&limit=20&active=true", cookies=admin_cookies
    )
    assert stages.status_code == 200
    items = stages.json()["items"]
    assert any(s["order_id"] == order_id for s in items), \
        f"order_id={order_id} not present in active production stages: {items}"
