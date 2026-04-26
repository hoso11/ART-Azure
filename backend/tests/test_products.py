import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_product(client: AsyncClient, admin_user, admin_cookies):
    # First create a category
    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Test Category",
    }, cookies=admin_cookies)
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    response = await client.post("/api/v1/products", json={
        "name": "Test Shirt",
        "sku": "TST-SHR-001",
        "category_id": cat_id,
        "description": "A test product",
        "variants": [
            {"size": "M", "color": "Blue", "price": 29.99, "stock_quantity": 100},
            {"size": "L", "color": "Blue", "price": 29.99, "stock_quantity": 50},
        ],
    }, cookies=admin_cookies)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Shirt"
    assert data["sku"] == "TST-SHR-001"
    assert len(data["variants"]) == 2


@pytest.mark.asyncio
async def test_list_products(client: AsyncClient, admin_user, admin_cookies):
    response = await client.get("/api/v1/products", cookies=admin_cookies)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_update_product(client: AsyncClient, admin_user, admin_cookies):
    # Create first
    create_resp = await client.post("/api/v1/products", json={
        "name": "Update Test",
        "sku": "TST-UPD-001",
    }, cookies=admin_cookies)
    product_id = create_resp.json()["id"]

    # Update
    response = await client.patch(f"/api/v1/products/{product_id}", json={
        "name": "Updated Name",
    }, cookies=admin_cookies)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_simple_user_cannot_create_product(client: AsyncClient, simple_user, user_cookies):
    response = await client.post("/api/v1/products", json={
        "name": "Forbidden",
        "sku": "TST-FBD-001",
    }, cookies=user_cookies)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_sku_rejected(client: AsyncClient, admin_user, admin_cookies):
    await client.post("/api/v1/products", json={
        "name": "First",
        "sku": "TST-DUP-001",
    }, cookies=admin_cookies)

    response = await client.post("/api/v1/products", json={
        "name": "Second",
        "sku": "TST-DUP-001",
    }, cookies=admin_cookies)
    assert response.status_code == 409
