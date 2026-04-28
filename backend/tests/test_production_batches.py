"""
Stock-based production batch tests (production-for-stock).

6 cases:
  1. Enough materials              → batch created (201), materials deducted
  2. Not enough materials          → 422, materials unchanged
  3. Complete production           → variant stock increases by quantity_to_produce
  4. Complete twice                → variant stock does NOT increase a second time
  5. Missing material requirements → 422 with clear "no_material_requirements" code
  6. Order-based production        → still works (smoke: confirm + transition to in_production)
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
async def test_complete_production_increases_variant_stock(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 3: completing a batch of 7 → variant stock_quantity goes 0 → 7."""
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

    # Variant stock is 0 before completion
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0

    complete = await client.patch(
        f"/api/v1/production/batches/{batch_id}/complete", cookies=admin_cookies
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["stage_status"] == "completed"
    assert body["stock_added"] is True
    assert body["completed_at"] is not None

    # Variant stock now 0 + 7 = 7
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 7


@pytest.mark.asyncio
async def test_complete_twice_does_not_double_stock(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 4: calling /complete twice on the same batch leaves variant stock unchanged after the first call."""
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

    first = await client.patch(
        f"/api/v1/production/batches/{batch_id}/complete", cookies=admin_cookies
    )
    assert first.status_code == 200
    stock_after_first = await _variant_stock(client, admin_cookies, product_id, variant_id)
    assert stock_after_first == 2 + 5  # initial 2 + produced 5

    # Second call must be a no-op for stock
    second = await client.patch(
        f"/api/v1/production/batches/{batch_id}/complete", cookies=admin_cookies
    )
    assert second.status_code == 200
    body = second.json()
    assert body["stock_added"] is True

    stock_after_second = await _variant_stock(client, admin_cookies, product_id, variant_id)
    assert stock_after_second == stock_after_first


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
