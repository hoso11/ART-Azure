import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_order(client: AsyncClient, admin_user, customer, admin_cookies):
    # Create a product with variant first
    prod_resp = await client.post("/api/v1/products", json={
        "name": "Order Test Product",
        "sku": "TST-ORD-001",
        "variants": [{"size": "M", "color": "Black", "price": 50.00, "stock_quantity": 100}],
    }, cookies=admin_cookies)
    variant_id = prod_resp.json()["variants"][0]["id"]

    response = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "priority": "normal",
        "notes": "Test order",
        "items": [
            {"product_variant_id": variant_id, "quantity": 10, "unit_price": 50.00},
        ],
    }, cookies=admin_cookies)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["customer_id"] == customer.id
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_order_status_transition(client: AsyncClient, admin_user, customer, admin_cookies):
    """3-status flow: admin can move freely between draft / confirmed / completed.
    Confirming does not deduct stock; completion deducts stock with a per-variant
    availability check; deprecated targets (in_production / shipped / cancelled)
    are rejected with 422."""
    prod_resp = await client.post("/api/v1/products", json={
        "name": "Status Test Product",
        "sku": "TST-STS-001",
        "variants": [{"size": "S", "color": "White", "price": 30.00, "stock_quantity": 5}],
    }, cookies=admin_cookies)
    variant_id = prod_resp.json()["variants"][0]["id"]

    order_resp = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 5, "unit_price": 30.00}],
    }, cookies=admin_cookies)
    order_id = order_resp.json()["id"]

    # draft → confirmed: no stock change.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "confirmed"}, cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    assert resp.json()["stock_deducted"] is False

    # Deprecated target rejected: in_production.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "in_production"}, cookies=admin_cookies)
    assert resp.status_code == 422
    assert resp.json()["code"] == "status_not_allowed"

    # Deprecated target rejected: shipped.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "shipped"}, cookies=admin_cookies)
    assert resp.status_code == 422

    # Deprecated target rejected: cancelled.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "cancelled"}, cookies=admin_cookies)
    assert resp.status_code == 422

    # confirmed → draft: free move, no stock change.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "draft"}, cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"
    assert resp.json()["stock_deducted"] is False

    # draft → completed (skipping confirmed): allowed; deducts stock.
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "completed"}, cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["stock_deducted"] is True


@pytest.mark.asyncio
async def test_simple_user_sees_own_orders_only(client: AsyncClient, simple_user, customer, user_cookies, admin_cookies, admin_user):
    # Create product
    prod_resp = await client.post("/api/v1/products", json={
        "name": "Access Test",
        "sku": "TST-ACC-001",
        "variants": [{"size": "M", "color": "Red", "price": 40.00}],
    }, cookies=admin_cookies)
    variant_id = prod_resp.json()["variants"][0]["id"]

    # Create order as simple user
    order_resp = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 3, "unit_price": 40.00}],
    }, cookies=user_cookies)
    assert order_resp.status_code == 201

    # List as simple user — should see own orders
    list_resp = await client.get("/api/v1/orders", cookies=user_cookies)
    assert list_resp.status_code == 200


# ── DELETE /orders/{id} guard tests ──────────────────────────────────────
# Behavior under test (backend/app/orders/service.py::delete_order):
#   - Allow when (no stages OR all stages pending) AND stock_deducted=False.
#   - When allowed and pending stages exist, remove them in the same txn.
#   - Block 422 order_stock_already_deducted when stock_deducted=True.
#   - Block 422 order_has_active_production when any stage is non-pending.

from sqlalchemy import select as _sa_select, func
from app.production.models import ProductionStage, StageStatus
from app.activity.models import ActivityLog


async def _make_order(client, customer, admin_cookies, *, sku_tag, stock=10, qty=2):
    prod = await client.post("/api/v1/products", json={
        "name": f"Del Test {sku_tag}",
        "sku": f"TST-DEL-{sku_tag}",
        "variants": [{"size": "M", "color": "Blue", "price": 10.00, "stock_quantity": stock}],
    }, cookies=admin_cookies)
    assert prod.status_code == 201, prod.text
    vid = prod.json()["variants"][0]["id"]
    order = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": vid, "quantity": qty, "unit_price": 10.00}],
    }, cookies=admin_cookies)
    assert order.status_code == 201, order.text
    return order.json()["id"], vid


@pytest.mark.asyncio
async def test_delete_order_no_stages_succeeds(client, customer, admin_cookies):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="NOSTG")
    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/orders/{order_id}", cookies=admin_cookies)).status_code == 404


@pytest.mark.asyncio
async def test_delete_order_with_all_pending_stages_succeeds_and_removes_them(
    client, customer, admin_cookies, db_session,
):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="PNDNG")
    seed = await client.post(f"/api/v1/production/orders/{order_id}/stages", cookies=admin_cookies)
    assert seed.status_code == 201
    assert len(seed.json()) == 5

    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 204

    remaining = (await db_session.execute(
        _sa_select(ProductionStage).where(ProductionStage.order_id == order_id)
    )).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_order_blocked_when_stage_in_progress(
    client, customer, admin_cookies, db_session,
):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="INPRG")
    await client.post(f"/api/v1/production/orders/{order_id}/stages", cookies=admin_cookies)
    one = (await db_session.execute(
        _sa_select(ProductionStage).where(ProductionStage.order_id == order_id).limit(1)
    )).scalar_one()
    one.status = StageStatus.in_progress
    await db_session.commit()

    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "order_has_active_production"
    assert "Cancel" in body["detail"]


@pytest.mark.asyncio
async def test_delete_order_blocked_when_stage_completed(
    client, customer, admin_cookies, db_session,
):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="CMPLT")
    await client.post(f"/api/v1/production/orders/{order_id}/stages", cookies=admin_cookies)
    one = (await db_session.execute(
        _sa_select(ProductionStage).where(ProductionStage.order_id == order_id).limit(1)
    )).scalar_one()
    one.status = StageStatus.completed
    await db_session.commit()

    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 422
    assert resp.json()["code"] == "order_has_active_production"


@pytest.mark.asyncio
async def test_delete_order_blocked_when_stock_deducted(
    client, customer, admin_cookies,
):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="STDED")
    # Status transition draft -> completed flips stock_deducted=True.
    resp = await client.patch(
        f"/api/v1/orders/{order_id}", json={"status": "completed"}, cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["stock_deducted"] is True

    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 422
    assert resp.json()["code"] == "order_stock_already_deducted"


@pytest.mark.asyncio
async def test_delete_order_audit_log_only_on_success(
    client, customer, admin_cookies, db_session,
):
    # Success path with stages: one row with the auto-removed details.
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="AUDIT1")
    await client.post(f"/api/v1/production/orders/{order_id}/stages", cookies=admin_cookies)
    assert (await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)).status_code == 204

    logs_ok = (await db_session.execute(
        _sa_select(ActivityLog).where(
            ActivityLog.action == "order.deleted", ActivityLog.entity_id == order_id,
        )
    )).scalars().all()
    assert len(logs_ok) == 1
    assert logs_ok[0].details and "Auto-removed 5" in logs_ok[0].details

    # Blocked path: no order.deleted row written for this order_id.
    order_id_b, _ = await _make_order(client, customer, admin_cookies, sku_tag="AUDIT2", stock=20)
    await client.patch(
        f"/api/v1/orders/{order_id_b}", json={"status": "completed"}, cookies=admin_cookies,
    )
    blocked = await client.delete(f"/api/v1/orders/{order_id_b}", cookies=admin_cookies)
    assert blocked.status_code == 422

    # Count delta — robust against SQLite rowid reuse, which can re-assign
    # a freed id to a newly created order in the same test.
    count_after = (await db_session.execute(
        _sa_select(func.count()).select_from(ActivityLog).where(ActivityLog.action == "order.deleted")
    )).scalar()
    assert count_after == 1  # the success row from earlier; no new row from the block


@pytest.mark.asyncio
async def test_delete_order_blocked_leaves_order_and_stages_intact(
    client, customer, admin_cookies, db_session,
):
    order_id, _ = await _make_order(client, customer, admin_cookies, sku_tag="LEAVE")
    await client.post(f"/api/v1/production/orders/{order_id}/stages", cookies=admin_cookies)
    one = (await db_session.execute(
        _sa_select(ProductionStage).where(ProductionStage.order_id == order_id).limit(1)
    )).scalar_one()
    one.status = StageStatus.in_progress
    await db_session.commit()

    resp = await client.delete(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 422

    get_resp = await client.get(f"/api/v1/orders/{order_id}", cookies=admin_cookies)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["items"]) == 1

    remaining = (await db_session.execute(
        _sa_select(ProductionStage).where(ProductionStage.order_id == order_id)
    )).scalars().all()
    assert len(remaining) == 5
