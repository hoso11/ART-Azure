"""
Completion-time stock-deduction tests for the 3-status order flow.

Migration 011 + service rewrite:
- draft / confirmed / completed are the three active statuses.
- Confirming does NOT touch stock.
- Completing deducts ProductVariant.stock_quantity once per order, gated by
  the new orders.stock_deducted boolean.
- Insufficient stock at completion → 422 with code='insufficient_stock', no
  partial deduction.
- Stock check is by exact product_variant_id (size + color); two items of
  the same product but different variants are debited independently.
- damaged_stock_quantity is never counted toward availability.
- Re-completion (e.g. completed → draft → completed) is a no-op: stock is
  not deducted again.
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


async def _add_variant(client, admin_cookies, product_id, *, size, color, stock_quantity, price=10.00):
    resp = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": size, "color": color, "price": price, "stock_quantity": stock_quantity},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_order(client, admin_cookies, *, customer_id, items):
    resp = await client.post(
        "/api/v1/orders",
        json={"customer_id": customer_id, "items": items},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _set_status(client, admin_cookies, order_id, status):
    return await client.patch(
        f"/api/v1/orders/{order_id}",
        json={"status": status},
        cookies=admin_cookies,
    )


async def _variant_stock(client, admin_cookies, product_id, variant_id) -> int:
    resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    for v in resp.json()["variants"]:
        if v["id"] == variant_id:
            return int(v["stock_quantity"])
    raise AssertionError(f"variant {variant_id} not found in product {product_id}")


async def _order(client, admin_cookies, order_id) -> dict:
    resp = await client.get(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_does_not_deduct_stock(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Confirming an order must NOT touch ProductVariant.stock_quantity."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-CONF-001", size="M", color="Black", stock_quantity=25,
    )
    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[{"product_variant_id": variant_id, "quantity": 5, "unit_price": 10.00}],
    )

    resp = await _set_status(client, admin_cookies, order_id, "confirmed")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"
    assert resp.json()["stock_deducted"] is False

    # Stock unchanged.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 25


@pytest.mark.asyncio
async def test_complete_with_sufficient_stock_deducts(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Completing with enough stock deducts ProductVariant.stock_quantity once."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-CMP-001", size="L", color="Blue", stock_quantity=20,
    )
    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[{"product_variant_id": variant_id, "quantity": 5, "unit_price": 10.00}],
    )

    # Confirm: no change.
    await _set_status(client, admin_cookies, order_id, "confirmed")
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 20

    # Complete: stock 20 - 5 = 15.
    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    assert resp.json()["stock_deducted"] is True
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 15


@pytest.mark.asyncio
async def test_complete_insufficient_stock_rejected_422(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Completing with insufficient stock → 422 'insufficient_stock', no deduction, status stays."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-SHORT-001", size="S", color="Yellow", stock_quantity=3,
    )
    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[{"product_variant_id": variant_id, "quantity": 10, "unit_price": 10.00}],
    )

    await _set_status(client, admin_cookies, order_id, "confirmed")

    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "insufficient_stock"
    assert "missing" in body.get("detail", "").lower()

    # Stock unchanged; order stays at confirmed; flag still false.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 3
    order = await _order(client, admin_cookies, order_id)
    assert order["status"] == "confirmed"
    assert order["stock_deducted"] is False


@pytest.mark.asyncio
async def test_complete_idempotent_no_double_deduction(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Re-completion after completed → draft → completed must NOT deduct again."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-IDEM-001", size="M", color="Pink", stock_quantity=20,
    )
    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[{"product_variant_id": variant_id, "quantity": 5, "unit_price": 10.00}],
    )

    # First complete: 20 - 5 = 15.
    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_deducted"] is True
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 15

    # completed → draft: no automatic stock reversal, flag stays True.
    resp = await _set_status(client, admin_cookies, order_id, "draft")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_deducted"] is True
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 15

    # draft → completed again: must NOT deduct again. Stock stays 15.
    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_deducted"] is True
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 15


@pytest.mark.asyncio
async def test_complete_per_variant_exact_match(
    client: AsyncClient, admin_user, customer, admin_cookies
):
    """Two items of the same product but different variants — only the matching
    variant's stock is debited."""
    product_id, vid_m = await _make_product(
        client, admin_cookies, sku="FF-EXACT-001", size="M", color="Red", stock_quantity=10,
    )
    vid_l = await _add_variant(
        client, admin_cookies, product_id, size="L", color="Red", stock_quantity=8,
    )

    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[
            {"product_variant_id": vid_m, "quantity": 3, "unit_price": 10.00},
            {"product_variant_id": vid_l, "quantity": 2, "unit_price": 10.00},
        ],
    )

    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 200, resp.text

    # M: 10 - 3 = 7; L: 8 - 2 = 6. No cross-variant leak.
    assert await _variant_stock(client, admin_cookies, product_id, vid_m) == 7
    assert await _variant_stock(client, admin_cookies, product_id, vid_l) == 6


@pytest.mark.asyncio
async def test_damaged_stock_does_not_count_toward_availability(
    client: AsyncClient, db_session, admin_user, customer, admin_cookies
):
    """damaged_stock_quantity is sellable-stock-separate. Even if a variant has
    plenty of damaged stock, the order must fail completion if sellable stock is
    insufficient."""
    from app.products.models import ProductVariant
    from sqlalchemy import select

    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="FF-DMG-001", size="M", color="Black", stock_quantity=2,
    )

    # Reach into the test DB to set damaged_stock_quantity (no public endpoint).
    result = await db_session.execute(
        select(ProductVariant).where(ProductVariant.id == variant_id)
    )
    v = result.scalar_one()
    v.damaged_stock_quantity = 100  # plenty of damaged units
    await db_session.commit()

    order_id = await _create_order(
        client, admin_cookies,
        customer_id=customer.id,
        items=[{"product_variant_id": variant_id, "quantity": 5, "unit_price": 10.00}],
    )

    resp = await _set_status(client, admin_cookies, order_id, "completed")
    assert resp.status_code == 422, resp.text
    assert resp.json().get("code") == "insufficient_stock"
    # damaged_stock_quantity should not appear in the shortage detail.
    assert "damaged" not in resp.json().get("detail", "").lower()

    # Sellable stock untouched.
    assert await _variant_stock(client, admin_cookies, product_id, variant_id) == 2
