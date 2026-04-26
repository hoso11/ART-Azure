import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_material(client: AsyncClient, admin_user, admin_cookies):
    response = await client.post("/api/v1/inventory/materials", json={
        "name": "Test Fabric",
        "sku": "MAT-TST-001",
        "unit": "meters",
        "low_stock_threshold": 10,
        "description": "Test material",
    }, cookies=admin_cookies)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Fabric"
    assert data["sku"] == "MAT-TST-001"


@pytest.mark.asyncio
async def test_stock_movement(client: AsyncClient, admin_user, admin_cookies):
    # Create material
    mat_resp = await client.post("/api/v1/inventory/materials", json={
        "name": "Movement Test",
        "sku": "MAT-MOV-001",
        "unit": "pieces",
        "low_stock_threshold": 5,
    }, cookies=admin_cookies)
    mat_id = mat_resp.json()["id"]

    # Add stock (purchase)
    response = await client.post("/api/v1/inventory/movements", json={
        "material_id": mat_id,
        "quantity_change": 100,
        "reason": "purchase",
    }, cookies=admin_cookies)
    assert response.status_code == 201
    assert float(response.json()["quantity_change"]) == 100.0

    # Remove stock (production usage)
    response = await client.post("/api/v1/inventory/movements", json={
        "material_id": mat_id,
        "quantity_change": -30,
        "reason": "production_usage",
    }, cookies=admin_cookies)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_duplicate_material_sku(client: AsyncClient, admin_user, admin_cookies):
    await client.post("/api/v1/inventory/materials", json={
        "name": "Dup Material",
        "sku": "MAT-DUP-001",
        "unit": "meters",
    }, cookies=admin_cookies)

    response = await client.post("/api/v1/inventory/materials", json={
        "name": "Dup Material 2",
        "sku": "MAT-DUP-001",
        "unit": "pieces",
    }, cookies=admin_cookies)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_simple_user_cannot_access_inventory(client: AsyncClient, simple_user, user_cookies):
    response = await client.get("/api/v1/inventory/materials", cookies=user_cookies)
    assert response.status_code == 403
