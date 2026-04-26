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
    # Create order
    prod_resp = await client.post("/api/v1/products", json={
        "name": "Status Test Product",
        "sku": "TST-STS-001",
        "variants": [{"size": "S", "color": "White", "price": 30.00}],
    }, cookies=admin_cookies)
    variant_id = prod_resp.json()["variants"][0]["id"]

    order_resp = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 5, "unit_price": 30.00}],
    }, cookies=admin_cookies)
    order_id = order_resp.json()["id"]

    # Valid transition: draft → confirmed
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "confirmed"}, cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    # Valid transition: confirmed → in_production
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "in_production"}, cookies=admin_cookies)
    assert resp.status_code == 200

    # Invalid transition: in_production → draft
    resp = await client.patch(f"/api/v1/orders/{order_id}", json={"status": "draft"}, cookies=admin_cookies)
    assert resp.status_code == 422


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
