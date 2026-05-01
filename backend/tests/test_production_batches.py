"""
Stock-based production batch tests (production-for-stock).

Cases:
  1. Enough materials                 → batch created (201), materials deducted
  2. Not enough materials             → 422, materials unchanged
  3. Complete all-good                → sellable stock += quantity, damaged unchanged
  4. Complete idempotent              → second /complete is a no-op (no double increment)
  5. Missing material requirements    → 422 with code="no_material_requirements"
  6. Order-based production           → still works (smoke: confirm + in_production)
  7. Partial complete (good+damaged)  → both counters increment correctly
  8. All damaged                      → damaged += quantity, sellable unchanged
  9. Sum != quantity_to_produce       → 422 with code="invalid_quantities"
 10. Negative good_quantity           → 422 with code="invalid_quantities"
 11. Negative damaged_quantity        → 422 with code="invalid_quantities"
 12. Materials stay deducted on any   → reject path (all-damaged) does NOT refund
 13. Single audit log on completion   → exactly one production.batch_completed
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
async def test_complete_idempotent_no_double_increment(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 4: a second /complete on an already-completed batch is a silent
    no-op — neither sellable nor damaged stock moves a second time."""
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

    first = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=2, reason="QC tears")
    assert first.status_code == 200, first.text
    sellable_after_first = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_after_first = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)
    assert sellable_after_first == 2 + 3  # initial 2 + produced 3 good
    assert damaged_after_first == 2

    # Second call — different quantities should NOT take effect.
    second = await _complete_batch(client, admin_cookies, batch_id, good=5, damaged=0)
    assert second.status_code == 200
    body = second.json()
    assert body["stock_added"] is True
    # The original split is preserved.
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
async def test_sum_not_equal_quantity_to_produce_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 9: sum != quantity_to_produce → 422 with code=invalid_quantities,
    no counters move. Tests both shrinkage (3+2 < 7) and overshoot (5+5 > 7)."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="PB-SUM-001", size="M", color="Yellow"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-SUM-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    create = await _create_batch(
        client, admin_cookies, product_id=product_id, variant_id=variant_id, quantity=7
    )
    batch_id = create.json()["id"]

    sellable_before = await _variant_stock(client, admin_cookies, product_id, variant_id)
    damaged_before = await _variant_damaged_stock(client, admin_cookies, product_id, variant_id)

    # Shrinkage attempt: 3 + 2 = 5 < 7 → rejected.
    short = await _complete_batch(client, admin_cookies, batch_id, good=3, damaged=2)
    assert short.status_code == 422
    assert short.json().get("code") == "invalid_quantities"

    # Overshoot attempt: 5 + 5 = 10 > 7 → rejected.
    over = await _complete_batch(client, admin_cookies, batch_id, good=5, damaged=5)
    assert over.status_code == 422
    assert over.json().get("code") == "invalid_quantities"

    # Counters unchanged.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == sellable_before
    assert await _variant_damaged_stock(client, admin_cookies, product_id, variant_id) == damaged_before


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
