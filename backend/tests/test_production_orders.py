"""Order-based production: one row per order via aggregation, free transitions, audit.

Covers:
  1. Existing 5-row seed unchanged.
  2. one_per_order=true returns exactly one row per active order.
  3. Admin can move stage forward via the new endpoint.
  4. Admin can move stage backward.
  5. Admin can jump (cutting → ready_for_shipment).
  6. Setting (cutting, completed) does NOT auto-advance later stages.
  7. Single-in-progress invariant after each PATCH.
  8. ONE ActivityLog entry per real change (even when multiple rows are touched).
  9. No-op PATCH writes no ActivityLog.
 10. Invalid stage / invalid status return 422 with code.
 11. Legacy per-row endpoints (PATCH /{stage_id}, PUT /{stage_id}/stage-status) still work.
 12. Status filter applies to the COMPUTED current status.
 13. Stock-based batch flow unaffected.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.production.models import (
    ProductionStage, ProductionLog, StageName, StageStatus, ProductionBatch,
)
from app.activity.models import ActivityLog


# ── helpers ─────────────────────────────────────────────────────────────────

async def _make_product_with_material(client, admin_cookies, *, sku, size="S"):
    p = await client.post("/api/v1/products", cookies=admin_cookies, json={
        "name": f"P-{sku}", "sku": sku,
        "variants": [{"size": size, "color": "Black", "price": 30.00}],
    })
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    vid = p.json()["variants"][0]["id"]
    m = await client.post("/api/v1/inventory/materials", cookies=admin_cookies, json={
        "name": f"M-{sku}", "sku": f"M-{sku}", "unit": "meters", "quantity_on_hand": 200,
    })
    mid = m.json()["id"]
    await client.post(f"/api/v1/products/{pid}/size-requirements", cookies=admin_cookies, json={
        "material_id": mid, "size": size, "quantity_per_item": 1,
    })
    return pid, vid


async def _create_in_production_order(client, customer, admin_cookies, vid):
    o = await client.post("/api/v1/orders", cookies=admin_cookies, json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": vid, "quantity": 2, "unit_price": 30.00}],
    })
    assert o.status_code == 201, o.text
    oid = o.json()["id"]
    r = await client.patch(f"/api/v1/orders/{oid}", cookies=admin_cookies, json={"status": "confirmed"})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/api/v1/orders/{oid}", cookies=admin_cookies, json={"status": "in_production"})
    assert r.status_code == 200, r.text
    return oid


async def _stage_count(db: AsyncSession, order_id: int) -> int:
    res = await db.execute(
        select(func.count()).select_from(ProductionStage).where(ProductionStage.order_id == order_id)
    )
    return res.scalar()


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_in_production_still_seeds_five_rows(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="SEED-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    assert await _stage_count(db_session, oid) == 5


@pytest.mark.asyncio
async def test_one_per_order_returns_single_row(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="OPO-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    r = await client.get(
        "/api/v1/production?one_per_order=true&active=true&limit=100",
        cookies=admin_cookies,
    )
    assert r.status_code == 200, r.text
    rows = [s for s in r.json()["items"] if s["order_id"] == oid]
    assert len(rows) == 1
    # Initial state: all pending → leftmost = cutting
    assert rows[0]["stage_name"] == "cutting"
    assert rows[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_set_current_forward(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="FWD-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current",
        cookies=admin_cookies,
        json={"current_stage": "sewing", "current_status": "in_progress"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage_name"] == "sewing"
    assert body["status"] == "in_progress"


@pytest.mark.asyncio
async def test_set_current_backward(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="BACK-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    # Forward to packaging.
    await client.patch(
        f"/api/v1/production/orders/{oid}/current",
        cookies=admin_cookies,
        json={"current_stage": "packaging", "current_status": "in_progress"},
    )
    # Backward to cutting.
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current",
        cookies=admin_cookies,
        json={"current_stage": "cutting", "current_status": "in_progress"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["stage_name"] == "cutting"
    assert r.json()["status"] == "in_progress"

    # List view also reflects backward move.
    list_r = await client.get(
        "/api/v1/production?one_per_order=true&active=true&limit=100",
        cookies=admin_cookies,
    )
    rows = [s for s in list_r.json()["items"] if s["order_id"] == oid]
    assert len(rows) == 1
    assert rows[0]["stage_name"] == "cutting"


@pytest.mark.asyncio
async def test_set_current_jump(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="JUMP-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current",
        cookies=admin_cookies,
        json={"current_stage": "ready_for_shipment", "current_status": "completed"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage_name"] == "ready_for_shipment"
    assert body["status"] == "completed"


@pytest.mark.asyncio
async def test_set_current_completed_does_not_auto_advance(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="NOAUTO-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current",
        cookies=admin_cookies,
        json={"current_stage": "cutting", "current_status": "completed"},
    )
    assert r.status_code == 200, r.text
    # Display: cutting/completed (rightmost non-pending = cutting).
    assert r.json()["stage_name"] == "cutting"
    assert r.json()["status"] == "completed"

    rows = (await db_session.execute(
        select(ProductionStage).where(ProductionStage.order_id == oid)
    )).scalars().all()
    by_name = {row.stage_name.value: row for row in rows}
    assert by_name["cutting"].status == StageStatus.completed
    assert by_name["sewing"].status == StageStatus.pending
    assert by_name["quality_control"].status == StageStatus.pending
    assert by_name["packaging"].status == StageStatus.pending
    assert by_name["ready_for_shipment"].status == StageStatus.pending


@pytest.mark.asyncio
async def test_single_in_progress_invariant(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="INV-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "cutting", "current_status": "in_progress"},
    )
    await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "sewing", "current_status": "in_progress"},
    )
    rows = (await db_session.execute(
        select(ProductionStage).where(ProductionStage.order_id == oid)
    )).scalars().all()
    in_progress = [r for r in rows if r.status == StageStatus.in_progress]
    assert len(in_progress) == 1
    assert in_progress[0].stage_name == StageName.sewing


@pytest.mark.asyncio
async def test_one_activity_log_per_change(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="AUD-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "packaging", "current_status": "in_progress"},
    )

    rows = (await db_session.execute(
        select(ActivityLog).where(ActivityLog.action == "production.order_current_changed")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].old_values == {"current_stage": "cutting", "current_status": "pending"}
    assert rows[0].new_values == {"current_stage": "packaging", "current_status": "in_progress"}


@pytest.mark.asyncio
async def test_noop_set_writes_no_log(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="NOOP-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    # Initial computed current is cutting/pending. PATCH same value → no-op.
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "cutting", "current_status": "pending"},
    )
    assert r.status_code == 200, r.text

    activity_count = (await db_session.execute(
        select(func.count()).select_from(ActivityLog)
        .where(ActivityLog.action == "production.order_current_changed")
    )).scalar()
    assert activity_count == 0


@pytest.mark.asyncio
async def test_invalid_stage_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="BAD-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "polishing", "current_status": "in_progress"},
    )
    assert r.status_code == 422
    assert r.json().get("code") == "invalid_stage"


@pytest.mark.asyncio
async def test_invalid_status_rejected(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="BAD-2")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "cutting", "current_status": "blocked"},
    )
    assert r.status_code == 422
    assert r.json().get("code") == "invalid_stage_status"


@pytest.mark.asyncio
async def test_warehousing_rejected_on_orders(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Warehousing is batch-only; not a valid order stage."""
    _, vid = await _make_product_with_material(client, admin_cookies, sku="WHS-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)
    r = await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "warehousing", "current_status": "in_progress"},
    )
    assert r.status_code == 422
    assert r.json().get("code") == "invalid_stage"


@pytest.mark.asyncio
async def test_legacy_per_row_endpoints_still_work(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="LEG-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    rows = (await db_session.execute(
        select(ProductionStage).where(ProductionStage.order_id == oid)
    )).scalars().all()
    cutting_id = next(r.id for r in rows if r.stage_name == StageName.cutting)

    # Legacy: advance cutting → sewing (adjacent, allowed).
    r = await client.patch(
        f"/api/v1/production/{cutting_id}", cookies=admin_cookies,
        json={"stage_name": "sewing"},
    )
    assert r.status_code == 200, r.text

    # Legacy status change.
    r = await client.put(
        f"/api/v1/production/{cutting_id}/stage-status", cookies=admin_cookies,
        json={"status": "in_progress"},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_status_filter_uses_computed_current(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    _, vid = await _make_product_with_material(client, admin_cookies, sku="FILT-1")
    oid = await _create_in_production_order(client, customer, admin_cookies, vid)

    # Move to sewing/in_progress.
    await client.patch(
        f"/api/v1/production/orders/{oid}/current", cookies=admin_cookies,
        json={"current_stage": "sewing", "current_status": "in_progress"},
    )

    # Filter for in_progress: order is included.
    r = await client.get(
        "/api/v1/production?one_per_order=true&active=true&status=in_progress&limit=100",
        cookies=admin_cookies,
    )
    assert r.status_code == 200, r.text
    in_prog_orders = [s["order_id"] for s in r.json()["items"]]
    assert oid in in_prog_orders

    # Filter for pending: order is NOT included (despite cutting row being completed
    # and qc/packaging/rfs being pending — the COMPUTED current is sewing/in_progress).
    r = await client.get(
        "/api/v1/production?one_per_order=true&active=true&status=pending&limit=100",
        cookies=admin_cookies,
    )
    pending_orders = [s["order_id"] for s in r.json()["items"]]
    assert oid not in pending_orders


@pytest.mark.asyncio
async def test_stock_based_batch_flow_unaffected(
    client: AsyncClient, db_session: AsyncSession, admin_user, customer, admin_cookies,
):
    pid, vid = await _make_product_with_material(client, admin_cookies, sku="STK-1", size="M")
    create = await client.post("/api/v1/production/batches", cookies=admin_cookies, json={
        "product_id": pid, "variant_id": vid, "quantity_to_produce": 3,
    })
    assert create.status_code == 201
    bid = create.json()["id"]
    r = await client.patch(
        f"/api/v1/production/batches/{bid}/complete",
        json={"good_quantity": 3, "damaged_quantity": 0},
        cookies=admin_cookies,
    )
    assert r.status_code == 200
    batch_count = (await db_session.execute(
        select(func.count()).select_from(ProductionBatch)
    )).scalar()
    assert batch_count >= 1
