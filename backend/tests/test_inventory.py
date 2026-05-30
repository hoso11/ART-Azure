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


# ── DELETE /inventory/materials/{id}/force — admin force-delete ────────────


async def _make_material_with_qty(client, admin_cookies, *, sku, qty=0):
    resp = await client.post(
        "/api/v1/inventory/materials",
        json={
            "name": f"Force {sku}",
            "sku": sku,
            "unit": "meters",
            "low_stock_threshold": 0,
            "quantity_on_hand": qty,
        },
        cookies=admin_cookies,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_user_with_role(db_session, role):
    """Local copy of the test-utility for RBAC sub-cases (test_inventory has
    no equivalent fixture; matches the helper in test_production_batches)."""
    from app.users.models import User
    from app.users.service import hash_password
    u = User(
        email=f"{role.value}@invforce.test.com",
        hashed_password=hash_password("Passw0rd!"),
        role=role,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


def _cookies_for_user(user):
    from app.auth.service import create_access_token
    return {"access_token": create_access_token(user.id, user.role.value)}


@pytest.mark.asyncio
async def test_force_delete_fresh_empty_material_succeeds(
    client: AsyncClient, admin_user, admin_cookies, db_session,
):
    """Material created with qty=0, no movements, no recipes → force-delete OK.
    Material AND its Inventory row are gone; ledger is unchanged (empty)."""
    from app.inventory.models import Material, Inventory
    from sqlalchemy import select as _sel
    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-OK-001", qty=0)

    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text

    # Material gone.
    mat = (await db_session.execute(
        _sel(Material).where(Material.id == mat_id)
    )).scalar_one_or_none()
    assert mat is None

    # Inventory row gone too.
    inv = (await db_session.execute(
        _sel(Inventory).where(Inventory.material_id == mat_id)
    )).scalar_one_or_none()
    assert inv is None


@pytest.mark.asyncio
async def test_force_delete_blocked_when_quantity_positive(
    client: AsyncClient, admin_user, admin_cookies,
):
    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-QTY-001", qty=5)
    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "material_quantity_not_zero"


@pytest.mark.asyncio
async def test_force_delete_blocked_when_stock_movements_exist(
    client: AsyncClient, admin_user, admin_cookies, db_session,
):
    """Stock-movement ledger must be preserved. Even if quantity nets to
    zero via two compensating movements, the rows still block force-delete."""
    from app.inventory.models import StockMovement
    from sqlalchemy import select as _sel

    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-MOV-001", qty=0)
    # Purchase 10 then production_usage -10 → quantity nets to 0; 2 ledger rows remain.
    await client.post("/api/v1/inventory/movements", json={
        "material_id": mat_id, "quantity_change": 10, "reason": "purchase",
    }, cookies=admin_cookies)
    await client.post("/api/v1/inventory/movements", json={
        "material_id": mat_id, "quantity_change": -10, "reason": "production_usage",
    }, cookies=admin_cookies)

    movement_count_before = (await db_session.execute(
        _sel(StockMovement).where(StockMovement.material_id == mat_id)
    )).scalars().all()
    assert len(movement_count_before) == 2

    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "material_has_stock_movements"

    # Ledger preserved.
    movement_count_after = (await db_session.execute(
        _sel(StockMovement).where(StockMovement.material_id == mat_id)
    )).scalars().all()
    assert len(movement_count_after) == 2


@pytest.mark.asyncio
async def test_force_delete_blocked_when_recipe_link_exists(
    client: AsyncClient, admin_user, admin_cookies,
):
    """A material used in a product size requirement cannot be force-deleted."""
    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-REC-001", qty=0)
    # Create a product, then link the material via a size requirement.
    prod_resp = await client.post("/api/v1/products", json={
        "name": "Recipe Holder", "sku": "PROD-FORCE-REC-001",
        "variants": [{"size": "M", "color": "Red", "price": 10.00}],
    }, cookies=admin_cookies)
    prod_id = prod_resp.json()["id"]
    await client.post(
        f"/api/v1/products/{prod_id}/size-requirements",
        json={"material_id": mat_id, "size": "M", "quantity_per_item": 1},
        cookies=admin_cookies,
    )

    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "material_has_recipe_links"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name",
    ["director", "production_manager", "warehouse_manager", "simple_user"],
)
async def test_force_delete_non_admin_forbidden(
    client: AsyncClient, admin_user, admin_cookies, db_session, role_name,
):
    from app.users.models import UserRole as _UR
    mat_id = await _make_material_with_qty(
        client, admin_cookies, sku=f"MAT-FORCE-RBAC-{role_name[:6]}", qty=0,
    )
    actor = await _make_user_with_role(db_session, _UR(role_name))
    actor_cookies = _cookies_for_user(actor)
    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=actor_cookies,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "insufficient_permissions"


@pytest.mark.asyncio
async def test_force_delete_writes_audit_row(
    client: AsyncClient, admin_user, admin_cookies, db_session,
):
    from app.activity.models import ActivityLog
    from sqlalchemy import func as _func, select as _sel
    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-AUD-001", qty=0)
    before = (await db_session.execute(
        _sel(_func.count()).select_from(ActivityLog)
        .where(ActivityLog.action == "inventory.material_force_deleted")
    )).scalar() or 0

    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204
    rows = (await db_session.execute(
        _sel(ActivityLog)
        .where(ActivityLog.action == "inventory.material_force_deleted")
    )).scalars().all()
    assert len(rows) - before == 1
    row = rows[-1]
    assert row.entity_type == "material"
    assert row.entity_id == mat_id
    assert row.details and "Force deleted" in row.details
    assert row.old_values["sku"] == "MAT-FORCE-AUD-001"


@pytest.mark.asyncio
async def test_force_delete_failed_attempt_writes_no_audit_row(
    client: AsyncClient, admin_user, admin_cookies, db_session,
):
    """A refused force-delete must not leave an audit trail of attempts."""
    from app.activity.models import ActivityLog
    from sqlalchemy import func as _func, select as _sel
    mat_id = await _make_material_with_qty(client, admin_cookies, sku="MAT-FORCE-FAIL-001", qty=3)
    before = (await db_session.execute(
        _sel(_func.count()).select_from(ActivityLog)
        .where(ActivityLog.action == "inventory.material_force_deleted")
    )).scalar() or 0

    resp = await client.delete(
        f"/api/v1/inventory/materials/{mat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422

    after = (await db_session.execute(
        _sel(_func.count()).select_from(ActivityLog)
        .where(ActivityLog.action == "inventory.material_force_deleted")
    )).scalar() or 0
    assert after == before
