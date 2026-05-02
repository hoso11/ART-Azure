"""
Sales / revenue report tests covering the per-customer filter.

Cases:
  1. No filter                    → response shape unchanged; selected_customer is None,
                                    order_items is empty; CSV filename = sales_report.csv.
  2. customer_id filter           → summary/by_day/by_customer reflect only that customer;
                                    selected_customer + order_items populated.
  3. CSV filename when filtered   → Content-Disposition contains
                                    customer-report-<slug>-<YYYY-MM-DD>.csv.
  4. CSV filename without filter  → Content-Disposition contains sales_report.csv.
  5. order_items totals match     → sum of order_items[*].total_price equals summary.total_revenue.
  6. Unknown customer_id          → 404 customer_not_found.
"""
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.customers.models import Customer


# ── helpers ─────────────────────────────────────────────────────────────────

async def _make_customer(db_session, name: str, company: str | None = None) -> Customer:
    c = Customer(name=name, company_name=company, email=f"{name.lower().replace(' ', '.')}@x.test")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


async def _make_product(client, admin_cookies, *, sku, size, color, price=10.00):
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"SR-{sku}",
            "sku": sku,
            "variants": [
                {"size": size, "color": color, "price": price, "stock_quantity": 0},
            ],
        },
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["id"], body["variants"][0]["id"], body["name"]


async def _create_order(client, admin_cookies, *, customer_id, items, status: str | None = None):
    resp = await client.post(
        "/api/v1/orders",
        json={"customer_id": customer_id, "items": items},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    order_id = resp.json()["id"]
    if status:
        s = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": status},
            cookies=admin_cookies,
        )
        assert s.status_code == 200, s.text
    return order_id


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sales_report_no_filter_unchanged(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """Case 1: legacy callers see the same shape — selected_customer None, order_items []."""
    cust = await _make_customer(db_session, "Cust A", "Co A")
    _, vid, _ = await _make_product(client, admin_cookies, sku="SR-NF-001", size="M", color="Black", price=100)
    await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid, "quantity": 2, "unit_price": 100}],
        status="confirmed",
    )

    resp = await client.get("/api/v1/reports/sales", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["selected_customer"] is None
    assert body["order_items"] == []
    assert "summary" in body
    assert "by_day" in body
    assert "by_customer" in body


@pytest.mark.asyncio
async def test_sales_report_customer_filter_returns_only_that_customer(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """Case 2: with customer_id, summary/by_day/by_customer scope to that customer."""
    cust_a = await _make_customer(db_session, "Cust A", "Co A")
    cust_b = await _make_customer(db_session, "Cust B", "Co B")
    _, vid, _ = await _make_product(client, admin_cookies, sku="SR-CF-001", size="M", color="Blue", price=200)

    # Two orders for A (confirmed → counted), one for B.
    await _create_order(
        client, admin_cookies, customer_id=cust_a.id,
        items=[{"product_variant_id": vid, "quantity": 3, "unit_price": 200}],
        status="confirmed",
    )
    await _create_order(
        client, admin_cookies, customer_id=cust_a.id,
        items=[{"product_variant_id": vid, "quantity": 1, "unit_price": 200}],
        status="confirmed",
    )
    await _create_order(
        client, admin_cookies, customer_id=cust_b.id,
        items=[{"product_variant_id": vid, "quantity": 5, "unit_price": 200}],
        status="confirmed",
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust_a.id}", cookies=admin_cookies
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["selected_customer"]["id"] == cust_a.id
    assert body["selected_customer"]["name"] == "Cust A"
    assert body["selected_customer"]["company_name"] == "Co A"

    # Only A's two orders counted.
    assert body["summary"]["total_orders"] == 2
    assert body["summary"]["confirmed_orders"] == 2
    assert body["summary"]["total_revenue"] == 800.0  # (3 + 1) * 200

    # by_customer must have exactly one row, scoped to A.
    assert len(body["by_customer"]) == 1
    assert body["by_customer"][0]["customer_name"] == "Cust A"
    assert body["by_customer"][0]["orders"] == 2
    assert body["by_customer"][0]["revenue"] == 800.0

    # order_items present — only A's items.
    assert len(body["order_items"]) == 2
    for row in body["order_items"]:
        assert row["product_name"] == "SR-SR-CF-001"  # _make_product prefixes name with SR-
        assert row["size"] == "M"
        assert row["color"] == "Blue"
        assert row["unit_price"] == 200.0
    quantities = sorted(r["quantity"] for r in body["order_items"])
    assert quantities == [1, 3]


@pytest.mark.asyncio
async def test_sales_report_csv_filename_when_filtered(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """Case 3: customer_id + format=csv → filename starts with customer-report-<slug>-<YYYY-MM-DD>."""
    cust = await _make_customer(db_session, "John Mitchell", "Mitchell & Co")
    _, vid, _ = await _make_product(client, admin_cookies, sku="SR-FN-001", size="S", color="Green", price=50)
    await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid, "quantity": 2, "unit_price": 50}],
        status="confirmed",
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust.id}&format=csv", cookies=admin_cookies
    )
    assert resp.status_code == 200, resp.text
    cd = resp.headers.get("content-disposition", "")
    today = date.today().isoformat()
    assert f"customer-report-john-mitchell-{today}.csv" in cd, cd

    # Body sanity — must have the new sections.
    text = resp.text
    assert "Selected Customer" in text
    assert "John Mitchell" in text
    assert "Order Items" in text
    assert "Order ID,Order Date,Product,SKU,Size,Color,Quantity,Unit Price,Total Price" in text


@pytest.mark.asyncio
async def test_sales_report_csv_filename_unchanged_without_filter(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """Case 4: no customer_id → filename stays sales_report.csv; no new CSV sections."""
    resp = await client.get(
        "/api/v1/reports/sales?format=csv", cookies=admin_cookies
    )
    assert resp.status_code == 200, resp.text
    cd = resp.headers.get("content-disposition", "")
    assert "sales_report.csv" in cd
    assert "customer-report-" not in cd

    text = resp.text
    assert "Selected Customer" not in text
    assert "Order Items" not in text


@pytest.mark.asyncio
async def test_sales_report_order_items_totals_match_revenue(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """Case 5: sum(order_items[*].total_price) == summary.total_revenue when filtered."""
    cust = await _make_customer(db_session, "TotalSum Co")
    _, vid_m, _ = await _make_product(client, admin_cookies, sku="SR-TS-001", size="M", color="Cyan", price=300)
    _, vid_l, _ = await _make_product(client, admin_cookies, sku="SR-TS-002", size="L", color="Magenta", price=450)

    # Two confirmed orders, mix of variants and quantities.
    await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[
            {"product_variant_id": vid_m, "quantity": 2, "unit_price": 300},
            {"product_variant_id": vid_l, "quantity": 1, "unit_price": 450},
        ],
        status="confirmed",
    )
    await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid_m, "quantity": 4, "unit_price": 300}],
        status="confirmed",
    )

    # One DRAFT order (not revenue-eligible) — must NOT show up in totals or items.
    await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid_l, "quantity": 99, "unit_price": 450}],
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust.id}", cookies=admin_cookies
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    items_total = sum(Decimal(str(i["total_price"])) for i in body["order_items"])
    assert items_total == Decimal(str(body["summary"]["total_revenue"]))
    # 2*300 + 1*450 + 4*300 = 600 + 450 + 1200 = 2250.
    assert body["summary"]["total_revenue"] == 2250.0
    # Three line items from the two confirmed orders only — the draft order's
    # single item must not appear.
    assert len(body["order_items"]) == 3
    assert all(i["order_id"] != 0 for i in body["order_items"])  # sanity
    assert not any(i["quantity"] == 99 for i in body["order_items"])


@pytest.mark.asyncio
async def test_sales_report_unknown_customer_id_404(
    client: AsyncClient, admin_user, admin_cookies
):
    """Case 6: customer_id that doesn't exist → 404 customer_not_found."""
    resp = await client.get(
        "/api/v1/reports/sales?customer_id=999999", cookies=admin_cookies
    )
    assert resp.status_code == 404
    assert resp.json().get("code") == "customer_not_found"


# ── order_id filter (Task: per-order export) ───────────────────────────────


@pytest.mark.asyncio
async def test_sales_report_filtered_by_customer_and_order_returns_only_that_order(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """customer_id + order_id → summary/by_day/by_customer/order_items reflect only that order."""
    cust = await _make_customer(db_session, "OneOrder Co")
    _, vid_a, _ = await _make_product(client, admin_cookies, sku="SR-OO-A", size="M", color="Red", price=100)
    _, vid_b, _ = await _make_product(client, admin_cookies, sku="SR-OO-B", size="L", color="Blue", price=200)

    target_order_id = await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[
            {"product_variant_id": vid_a, "quantity": 2, "unit_price": 100},
            {"product_variant_id": vid_b, "quantity": 1, "unit_price": 200},
        ],
        status="confirmed",
    )
    # Second confirmed order for the same customer — must NOT appear when filtering.
    other_order_id = await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid_a, "quantity": 5, "unit_price": 100}],
        status="confirmed",
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust.id}&order_id={target_order_id}",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["selected_customer"]["id"] == cust.id
    assert body["selected_order"]["id"] == target_order_id
    assert body["selected_order"]["status"] == "confirmed"

    # Only the target order's totals: 2*100 + 1*200 = 400.
    assert body["summary"]["total_orders"] == 1
    assert body["summary"]["confirmed_orders"] == 1
    assert body["summary"]["total_revenue"] == 400.0

    # by_customer scoped to one row, the target customer.
    assert len(body["by_customer"]) == 1
    assert body["by_customer"][0]["orders"] == 1
    assert body["by_customer"][0]["revenue"] == 400.0

    # order_items only from target order; the other order's vid_a quantity=5 row must not appear.
    assert len(body["order_items"]) == 2
    assert all(i["order_id"] == target_order_id for i in body["order_items"])
    quantities = sorted(i["quantity"] for i in body["order_items"])
    assert quantities == [1, 2]
    # Sanity: the unrelated order id is absent.
    assert all(i["order_id"] != other_order_id for i in body["order_items"])


@pytest.mark.asyncio
async def test_sales_report_csv_filename_includes_order_id(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """CSV with customer_id + order_id → filename contains -order-<id>- and body has Selected Order section."""
    cust = await _make_customer(db_session, "Modamio", "Modamio LLC")
    _, vid, _ = await _make_product(client, admin_cookies, sku="SR-FN-OID", size="S", color="Black", price=75)
    order_id = await _create_order(
        client, admin_cookies, customer_id=cust.id,
        items=[{"product_variant_id": vid, "quantity": 4, "unit_price": 75}],
        status="confirmed",
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust.id}&order_id={order_id}&format=csv",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200, resp.text
    cd = resp.headers.get("content-disposition", "")
    today = date.today().isoformat()
    assert f"customer-report-modamio-order-{order_id}-{today}.csv" in cd, cd

    text = resp.text
    assert "Selected Customer" in text
    assert "Selected Order" in text
    assert str(order_id) in text
    assert "Order Items" in text


@pytest.mark.asyncio
async def test_sales_report_order_id_without_customer_id_422(
    client: AsyncClient, admin_user, admin_cookies
):
    """order_id without customer_id → 422 order_id_requires_customer_id."""
    resp = await client.get(
        "/api/v1/reports/sales?order_id=1", cookies=admin_cookies
    )
    assert resp.status_code == 422
    assert resp.json().get("code") == "order_id_requires_customer_id"


@pytest.mark.asyncio
async def test_sales_report_order_id_for_different_customer_422(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """order_id that belongs to a different customer → 422 order_not_for_customer."""
    cust_a = await _make_customer(db_session, "Owner A")
    cust_b = await _make_customer(db_session, "Other B")
    _, vid, _ = await _make_product(client, admin_cookies, sku="SR-XCUST", size="M", color="Pink", price=10)
    order_for_a = await _create_order(
        client, admin_cookies, customer_id=cust_a.id,
        items=[{"product_variant_id": vid, "quantity": 1, "unit_price": 10}],
        status="confirmed",
    )

    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust_b.id}&order_id={order_for_a}",
        cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json().get("code") == "order_not_for_customer"


@pytest.mark.asyncio
async def test_sales_report_unknown_order_id_404(
    client: AsyncClient, db_session, admin_user, admin_cookies
):
    """customer_id valid, order_id missing → 404 order_not_found."""
    cust = await _make_customer(db_session, "ValidCust")
    resp = await client.get(
        f"/api/v1/reports/sales?customer_id={cust.id}&order_id=999999",
        cookies=admin_cookies,
    )
    assert resp.status_code == 404
    assert resp.json().get("code") == "order_not_found"
