"""
Damaged-stock (Խոտան) report tests.

Cases:
  1. Empty: no batches → totals all 0, items=[]
  2. After partial completion: 5 good + 2 damaged → total_damaged=2, one item
  3. Multiple batches on same variant: damaged accumulates
  4. Variants with 0 damaged are excluded from items
  5. CSV export returns expected text
  6. Existing reports still work (smoke: /reports/inventory)
  7. Sellable stock is NOT counted as damaged (rule 4 of the task)
"""
import pytest
from httpx import AsyncClient


# ── helpers ─────────────────────────────────────────────────────────────────

async def _make_product(client, admin_cookies, *, sku, size, color, stock_quantity=0):
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"DR-{sku}",
            "sku": sku,
            "variants": [
                {"size": size, "color": color, "price": 10, "stock_quantity": stock_quantity},
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
        json={"name": f"DR-Mat-{sku}", "sku": sku, "unit": "meters", "quantity_on_hand": qty},
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


async def _create_and_complete(
    client, admin_cookies, *, product_id, variant_id, quantity, good, damaged,
):
    create = await client.post(
        "/api/v1/production/batches",
        json={
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity_to_produce": quantity,
        },
        cookies=admin_cookies,
    )
    assert create.status_code == 201, create.text
    batch_id = create.json()["id"]
    body = {"good_quantity": good, "damaged_quantity": damaged}
    if damaged > 0:
        body["defect_reason"] = f"{damaged} units rejected at QC"
    complete = await client.patch(
        f"/api/v1/production/batches/{batch_id}/complete",
        json=body, cookies=admin_cookies,
    )
    assert complete.status_code == 200, complete.text
    return batch_id


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_damaged_stock_report_empty(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 1: with no defective batches anywhere, totals are 0 and items=[]."""
    resp = await client.get("/api/v1/reports/damaged-stock", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["total_damaged"] == 0
    assert data["summary"]["products_affected"] == 0
    assert data["summary"]["variants_affected"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_damaged_stock_report_after_partial_complete(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 2: 5 good + 2 damaged on one variant → report shows total=2, one row."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="DR-PARTIAL-001", size="S", color="Khaki"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DR-001", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="S", qty_per_item=1
    )

    await _create_and_complete(
        client, admin_cookies, product_id=product_id, variant_id=variant_id,
        quantity=7, good=5, damaged=2,
    )

    resp = await client.get("/api/v1/reports/damaged-stock", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_damaged"] == 2
    assert data["summary"]["products_affected"] == 1
    assert data["summary"]["variants_affected"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["product_id"] == product_id
    assert item["variant_id"] == variant_id
    assert item["sku"] == "DR-PARTIAL-001"
    assert item["size"] == "S"
    assert item["color"] == "Khaki"
    assert item["damaged_stock_quantity"] == 2


@pytest.mark.asyncio
async def test_damaged_stock_aggregates_multiple_batches(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 3: two batches on the same variant → damaged counter accumulates,
    still one row in the report."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="DR-AGG-001", size="M", color="Black"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DR-002", qty=200)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    await _create_and_complete(
        client, admin_cookies, product_id=product_id, variant_id=variant_id,
        quantity=4, good=3, damaged=1,
    )
    await _create_and_complete(
        client, admin_cookies, product_id=product_id, variant_id=variant_id,
        quantity=5, good=2, damaged=3,
    )

    resp = await client.get("/api/v1/reports/damaged-stock", cookies=admin_cookies)
    data = resp.json()
    assert data["summary"]["total_damaged"] == 4  # 1 + 3
    assert data["summary"]["variants_affected"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["damaged_stock_quantity"] == 4


@pytest.mark.asyncio
async def test_damaged_stock_excludes_zero_damaged_variants(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 4: a variant completed entirely as good must NOT appear in items.
    Sellable stock must NOT be counted as damaged."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="DR-ZERO-001", size="L", color="Blue", stock_quantity=10
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DR-003", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="L", qty_per_item=1
    )

    # All-good completion → no damaged stock added.
    await _create_and_complete(
        client, admin_cookies, product_id=product_id, variant_id=variant_id,
        quantity=4, good=4, damaged=0,
    )

    resp = await client.get("/api/v1/reports/damaged-stock", cookies=admin_cookies)
    data = resp.json()
    assert data["summary"]["total_damaged"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_damaged_stock_csv_export(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 5: ?format=csv returns text/csv with summary header, totals,
    and a row per damaged variant."""
    product_id, variant_id = await _make_product(
        client, admin_cookies, sku="DR-CSV-001", size="M", color="Red"
    )
    material_id = await _make_material(client, admin_cookies, sku="MAT-DR-004", qty=100)
    await _add_size_requirement(
        client, admin_cookies, product_id=product_id, material_id=material_id, size="M", qty_per_item=1
    )

    await _create_and_complete(
        client, admin_cookies, product_id=product_id, variant_id=variant_id,
        quantity=3, good=1, damaged=2,
    )

    resp = await client.get(
        "/api/v1/reports/damaged-stock?format=csv", cookies=admin_cookies
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "damaged_stock_report.csv" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "Damaged Stock Report Summary" in body
    assert "Total Damaged,2" in body
    assert "DR-CSV-001" in body
    assert ",M,Red,2" in body  # the variant row


@pytest.mark.asyncio
async def test_existing_inventory_report_still_works(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 6: smoke — adding a damaged-stock report did not break the
    existing /reports/inventory endpoint."""
    resp = await client.get("/api/v1/reports/inventory", cookies=admin_cookies)
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_damaged_stock_separate_from_sellable_stock(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Case 7 (rule 4): a variant with non-zero sellable stock_quantity but
    zero damaged_stock_quantity is NOT in the damaged report."""
    # Sellable stock seeded directly via product create — no production involved,
    # so damaged_stock_quantity stays at 0.
    await _make_product(
        client, admin_cookies, sku="DR-SELL-001", size="S", color="Olive", stock_quantity=50
    )

    resp = await client.get("/api/v1/reports/damaged-stock", cookies=admin_cookies)
    data = resp.json()
    skus_in_report = {it["sku"] for it in data["items"]}
    assert "DR-SELL-001" not in skus_in_report
    # And the totals aren't incremented by the 50 sellable units.
    assert data["summary"]["total_damaged"] == 0
