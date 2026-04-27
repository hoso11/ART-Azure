"""
Stock-first order fulfillment tests.

Verifies the already-implemented logic in app.orders.service._fulfill_order_items
without changing any business code. Five cases:

  1. Enough stock              → variant decremented, no material deduction
  2. Partial stock             → variant to 0, materials deducted only for the deficit
  3. No stock                  → materials deducted for full ordered quantity
  4. Insufficient raw material → confirmation fails, variant + materials unchanged
  5. Double confirmation       → second confirm rejected, no double deduction
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── helpers ─────────────────────────────────────────────────────────────────

async def _make_product(client, admin_cookies, *, sku, size, color, stock_quantity, price=10.00):
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"FF-{sku}",
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
        json={"name": f"FF-Mat-{sku}", "sku": sku, "unit": "meters", "quantity_on_hand": qty},
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


async def _create_order(client, admin_cookies, *, customer_id, variant_id, quantity, unit_price=10.00):
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "items": [{"product_variant_id": variant_id, "quantity": quantity, "unit_price": unit_price}],
        },
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _confirm(client, admin_cookies, order_id):
    return await client.patch(
        f"/api/v1/orders/{order_id}",
        json={"status": "confirmed"},
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


async def _order(client, admin_cookies, order_id) -> dict:
    resp = await client.get(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enough_stock_no_production_no_material_deduction(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 1: stock 25, order 5 → stock 20, no material deduction, production_quantity = 0."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-ENOUGH-001", size="M", color="Black", stock_quantity=25,
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-ENOUGH-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2,
    )

    order_id = await _create_order(
        client, admin_cookies, customer_id=customer.id, variant_id=variant_id, quantity=5,
    )

    resp = await _confirm(client, admin_cookies, order_id)
    assert resp.status_code == 200, resp.text

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 20
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("100")

    item = (await _order(client, admin_cookies, order_id))["items"][0]
    assert item["fulfilled_from_stock"] == 5
    assert item["production_quantity"] == 0


@pytest.mark.asyncio
async def test_partial_stock_deducts_materials_only_for_deficit(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 2: stock 25, order 30 → stock 0, production_quantity 5, materials deducted for 5×2=10."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-PARTIAL-001", size="L", color="Blue", stock_quantity=25,
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-PARTIAL-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="L", qty_per_item=2,
    )

    order_id = await _create_order(
        client, admin_cookies, customer_id=customer.id, variant_id=variant_id, quantity=30,
    )

    resp = await _confirm(client, admin_cookies, order_id)
    assert resp.status_code == 200, resp.text

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0
    # 100 - (5 to_produce * 2 per item) = 90
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("90")

    item = (await _order(client, admin_cookies, order_id))["items"][0]
    assert item["fulfilled_from_stock"] == 25
    assert item["production_quantity"] == 5


@pytest.mark.asyncio
async def test_no_stock_full_production_full_material_deduction(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 3: stock 0, order 10 → stock stays 0, production_quantity 10, materials -30."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-NONE-001", size="S", color="Green", stock_quantity=0,
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-NONE-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="S", qty_per_item=3,
    )

    order_id = await _create_order(
        client, admin_cookies, customer_id=customer.id, variant_id=variant_id, quantity=10,
    )

    resp = await _confirm(client, admin_cookies, order_id)
    assert resp.status_code == 200, resp.text

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0
    # 100 - (10 * 3) = 70
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("70")

    item = (await _order(client, admin_cookies, order_id))["items"][0]
    assert item["fulfilled_from_stock"] == 0
    assert item["production_quantity"] == 10


@pytest.mark.asyncio
async def test_insufficient_materials_rolls_back_everything(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 4: need 20m but only 5m on hand → 422, variant + material unchanged, order stays draft."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-SHORT-001", size="M", color="Yellow", stock_quantity=0,
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-SHORT-001", qty=5)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2,
    )

    order_id = await _create_order(
        client, admin_cookies, customer_id=customer.id, variant_id=variant_id, quantity=10,
    )

    resp = await _confirm(client, admin_cookies, order_id)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "insufficient_materials"

    # Nothing mutated.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 0
    assert await _material_qty(client, admin_cookies, material_id) == Decimal("5")

    order = await _order(client, admin_cookies, order_id)
    assert order["status"] == "draft"
    assert order["items"][0]["fulfilled_from_stock"] == 0
    assert order["items"][0]["production_quantity"] == 0


@pytest.mark.asyncio
async def test_double_confirmation_does_not_deduct_twice(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Case 5: confirming an already-confirmed order must not deduct stock or materials again."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-DBL-001", size="M", color="Pink", stock_quantity=5,
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DBL-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=2,
    )

    order_id = await _create_order(
        client, admin_cookies, customer_id=customer.id, variant_id=variant_id, quantity=10,
    )

    # First confirm: 5 from stock, 5 to produce → variant 0, material 100 - 5*2 = 90
    resp1 = await _confirm(client, admin_cookies, order_id)
    assert resp1.status_code == 200, resp1.text

    stock_after_first = await _variant_stock(client, admin_cookies, product_id, variant_id)
    material_after_first = await _material_qty(client, admin_cookies, material_id)
    assert stock_after_first == 0
    assert material_after_first == Decimal("90")

    # Second confirm: status-transition guard rejects confirmed→confirmed (422),
    # and even if it did pass, materials_deducted=True would short-circuit the deduction.
    # Either way, no double mutation.
    resp2 = await _confirm(client, admin_cookies, order_id)
    assert resp2.status_code == 422

    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == stock_after_first
    assert await _material_qty(client, admin_cookies, material_id) == material_after_first
