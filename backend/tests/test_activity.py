"""Audit log / activity history tests.

Covers:
  - log_activity write semantics (fields, denormalized email, IP, graceful failure)
  - extract_ip honors X-Forwarded-For
  - GET /activity-logs admin gate, pagination, filters
  - Real mutation paths produce the expected audit rows:
      * login success / failure
      * user CRUD + password change separation
      * order create / status change (with materials_deducted summary)
      * production batch create / complete (idempotency)
      * report generation
  - Sensitive data (password hash) never appears in any audit row
"""
from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import service as activity_service
from app.activity.models import ActivityLog


# ── helpers ─────────────────────────────────────────────────────────────────

async def _all_logs(db: AsyncSession) -> list[ActivityLog]:
    res = await db.execute(select(ActivityLog).order_by(ActivityLog.created_at.asc()))
    return list(res.scalars().all())


async def _logs_with_action(db: AsyncSession, action: str) -> list[ActivityLog]:
    res = await db.execute(select(ActivityLog).where(ActivityLog.action == action))
    return list(res.scalars().all())


# ── unit tests for log_activity / extract_ip ──────────────────────────────

@pytest.mark.asyncio
async def test_extract_ip_prefers_xff():
    class _Req:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        client = type("C", (), {"host": "127.0.0.1"})()
    assert activity_service.extract_ip(_Req()) == "203.0.113.7"


@pytest.mark.asyncio
async def test_extract_ip_falls_back_to_client_host():
    class _Req:
        headers = {}
        client = type("C", (), {"host": "10.0.0.5"})()
    assert activity_service.extract_ip(_Req()) == "10.0.0.5"


@pytest.mark.asyncio
async def test_extract_ip_handles_no_request():
    assert activity_service.extract_ip(None) is None


@pytest.mark.asyncio
async def test_log_activity_writes_full_row(db_session: AsyncSession, admin_user):
    log = await activity_service.log_activity(
        db_session, user=admin_user,
        action="test.action", entity_type="thing", entity_id=42,
        old_values={"x": 1}, new_values={"x": 2}, details="hi",
        request=None,
    )
    await db_session.commit()
    assert log is not None
    assert log.user_id == admin_user.id
    assert log.user_email == admin_user.email  # denormalized snapshot
    assert log.action == "test.action"
    assert log.entity_type == "thing"
    assert log.entity_id == 42
    assert log.old_values == {"x": 1}
    assert log.new_values == {"x": 2}
    assert log.details == "hi"
    assert log.ip_address is None
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_log_activity_user_none_is_ok(db_session: AsyncSession):
    log = await activity_service.log_activity(
        db_session, user=None,
        action="auth.login_failed", entity_type="auth",
        details="email=ghost@example.com",
    )
    await db_session.commit()
    assert log is not None
    assert log.user_id is None
    assert log.user_email is None


@pytest.mark.asyncio
async def test_log_activity_swallows_db_error(db_session: AsyncSession, admin_user, monkeypatch):
    # Force a flush failure — log_activity must NOT raise; the parent
    # mutation should remain unaffected.
    async def _boom(*a, **kw):
        raise RuntimeError("simulated flush failure")
    monkeypatch.setattr(db_session, "flush", _boom)
    result = await activity_service.log_activity(
        db_session, user=admin_user, action="x", entity_type="y",
    )
    assert result is None


# ── API: admin gate + pagination + filters ─────────────────────────────────

@pytest.mark.asyncio
async def test_activity_logs_requires_admin(client: AsyncClient, simple_user, user_cookies):
    r = await client.get("/api/v1/activity-logs", cookies=user_cookies)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_activity_logs_unauthenticated_rejected(client: AsyncClient):
    r = await client.get("/api/v1/activity-logs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_activity_logs_paginated_newest_first(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    for i in range(5):
        await activity_service.log_activity(
            db_session, user=admin_user, action=f"test.{i}", entity_type="t", entity_id=i,
        )
    await db_session.commit()

    r = await client.get("/api/v1/activity-logs?page=1&limit=3", cookies=admin_cookies)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 3
    # Newest first
    assert body["items"][0]["action"] == "test.4"
    assert body["items"][2]["action"] == "test.2"


@pytest.mark.asyncio
async def test_activity_logs_filter_by_entity_type_and_action(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    await activity_service.log_activity(db_session, user=admin_user, action="user.created", entity_type="user")
    await activity_service.log_activity(db_session, user=admin_user, action="order.created", entity_type="order")
    await activity_service.log_activity(db_session, user=admin_user, action="order.deleted", entity_type="order")
    await db_session.commit()

    r = await client.get("/api/v1/activity-logs?entity_type=order", cookies=admin_cookies)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r = await client.get("/api/v1/activity-logs?action=order.created", cookies=admin_cookies)
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_activity_logs_filter_by_date_range(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    # Backdate one row.
    await activity_service.log_activity(db_session, user=admin_user, action="old", entity_type="t")
    await db_session.commit()
    backdated = (await _all_logs(db_session))[0]
    backdated.created_at = datetime.utcnow() - timedelta(days=10)
    await db_session.commit()

    await activity_service.log_activity(db_session, user=admin_user, action="new", entity_type="t")
    await db_session.commit()

    cutoff = (datetime.utcnow() - timedelta(days=1)).isoformat()
    r = await client.get(f"/api/v1/activity-logs?from_date={cutoff}", cookies=admin_cookies)
    assert r.status_code == 200
    actions = [i["action"] for i in r.json()["items"]]
    assert "new" in actions
    assert "old" not in actions


# ── End-to-end: mutation endpoints write the right rows ───────────────────

@pytest.mark.asyncio
async def test_login_success_writes_audit(client: AsyncClient, db_session: AsyncSession, admin_user):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "adminpass123",
    })
    assert r.status_code == 200
    rows = await _logs_with_action(db_session, "auth.login_success")
    assert len(rows) == 1
    assert rows[0].user_id == admin_user.id
    assert rows[0].user_email == "admin@test.com"
    assert rows[0].entity_type == "auth"


@pytest.mark.asyncio
async def test_login_failure_writes_audit_with_email_in_details(
    client: AsyncClient, db_session: AsyncSession, admin_user
):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "wrong",
    })
    assert r.status_code == 401
    rows = await _logs_with_action(db_session, "auth.login_failed")
    assert len(rows) == 1
    assert rows[0].user_id is None
    assert rows[0].user_email is None
    assert "admin@test.com" in (rows[0].details or "")


@pytest.mark.asyncio
async def test_login_failure_for_unknown_user_still_logs(
    client: AsyncClient, db_session: AsyncSession
):
    r = await client.post("/api/v1/auth/login", json={
        "email": "ghost@example.com", "password": "anything",
    })
    assert r.status_code == 401
    rows = await _logs_with_action(db_session, "auth.login_failed")
    assert len(rows) == 1
    assert "ghost@example.com" in (rows[0].details or "")


@pytest.mark.asyncio
async def test_xff_header_recorded_as_ip(
    client: AsyncClient, db_session: AsyncSession, admin_user
):
    await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "adminpass123"},
        headers={"X-Forwarded-For": "198.51.100.42"},
    )
    rows = await _logs_with_action(db_session, "auth.login_success")
    assert rows[0].ip_address == "198.51.100.42"


@pytest.mark.asyncio
async def test_user_create_and_password_change_audited_separately(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    create_r = await client.post(
        "/api/v1/users",
        json={"email": "new@test.com", "password": "secret123!", "role": "simple_user"},
        cookies=admin_cookies,
    )
    assert create_r.status_code == 201
    new_id = create_r.json()["id"]

    # Update with both a password and a non-sensitive field → 2 rows.
    upd_r = await client.patch(
        f"/api/v1/users/{new_id}",
        json={"password": "newsecret123!", "discount_percent": 15},
        cookies=admin_cookies,
    )
    assert upd_r.status_code == 200

    created = await _logs_with_action(db_session, "user.created")
    assert len(created) == 1
    assert created[0].new_values["email"] == "new@test.com"
    # No password hash should ever land in an audit row.
    for row in await _all_logs(db_session):
        for blob in (row.old_values, row.new_values):
            if blob:
                for v in blob.values():
                    assert "$2b$" not in str(v), "bcrypt hash leaked into audit"

    pw = await _logs_with_action(db_session, "user.password_changed")
    assert len(pw) == 1
    assert pw[0].old_values is None
    assert pw[0].new_values is None
    assert pw[0].details == "Password changed"

    discount = await _logs_with_action(db_session, "user.discount_changed")
    assert len(discount) == 1
    assert discount[0].old_values == {"discount_percent": 0}
    assert discount[0].new_values == {"discount_percent": 15}


@pytest.mark.asyncio
async def test_user_delete_preserves_email_snapshot(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    r = await client.post(
        "/api/v1/users",
        json={"email": "doomed@test.com", "password": "p123456789"},
        cookies=admin_cookies,
    )
    uid = r.json()["id"]
    await client.delete(f"/api/v1/users/{uid}", cookies=admin_cookies)

    rows = await _logs_with_action(db_session, "user.deleted")
    assert len(rows) == 1
    assert rows[0].old_values["email"] == "doomed@test.com"
    assert "doomed@test.com" in (rows[0].details or "")


@pytest.mark.asyncio
async def test_order_status_change_and_materials_deduction_one_row(
    client: AsyncClient, db_session: AsyncSession,
    admin_user, customer, admin_cookies,
):
    # Make a product+variant+material+requirement, then create+confirm an order.
    p = await client.post("/api/v1/products", cookies=admin_cookies, json={
        "name": "P", "sku": "AUDIT-1",
        "variants": [{"size": "M", "color": "Black", "price": 10}],
    })
    assert p.status_code == 201
    pid = p.json()["id"]
    vid = p.json()["variants"][0]["id"]

    m = await client.post("/api/v1/inventory/materials", cookies=admin_cookies, json={
        "name": "Fabric", "sku": "AUD-MAT-1", "unit": "meters", "quantity_on_hand": 100,
    })
    mid = m.json()["id"]

    await client.post(f"/api/v1/products/{pid}/size-requirements", cookies=admin_cookies, json={
        "material_id": mid, "size": "M", "quantity_per_item": 2,
    })

    o = await client.post("/api/v1/orders", cookies=admin_cookies, json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": vid, "quantity": 3, "unit_price": 10}],
    })
    assert o.status_code == 201
    oid = o.json()["id"]

    created = await _logs_with_action(db_session, "order.created")
    assert len(created) == 1
    assert created[0].entity_id == oid

    # Confirm → triggers material deduction. Expect ONE summary status_changed row.
    r = await client.patch(f"/api/v1/orders/{oid}", cookies=admin_cookies, json={"status": "confirmed"})
    assert r.status_code == 200
    status_rows = await _logs_with_action(db_session, "order.status_changed")
    assert len(status_rows) == 1
    assert status_rows[0].old_values == {"status": "draft"}
    assert status_rows[0].new_values["status"] == "confirmed"
    assert status_rows[0].new_values["materials_deducted"] is True
    assert status_rows[0].details == "Materials deducted on confirmation"


@pytest.mark.asyncio
async def test_batch_create_and_complete_audited_idempotent(
    client: AsyncClient, db_session: AsyncSession,
    admin_user, customer, admin_cookies,
):
    p = await client.post("/api/v1/products", cookies=admin_cookies, json={
        "name": "P", "sku": "AUDIT-2",
        "variants": [{"size": "L", "color": "Blue", "price": 12, "stock_quantity": 0}],
    })
    pid = p.json()["id"]
    vid = p.json()["variants"][0]["id"]
    m = await client.post("/api/v1/inventory/materials", cookies=admin_cookies, json={
        "name": "Fabric", "sku": "AUD-MAT-2", "unit": "meters", "quantity_on_hand": 100,
    })
    mid = m.json()["id"]
    await client.post(f"/api/v1/products/{pid}/size-requirements", cookies=admin_cookies, json={
        "material_id": mid, "size": "L", "quantity_per_item": 1,
    })

    create = await client.post("/api/v1/production/batches", cookies=admin_cookies, json={
        "product_id": pid, "variant_id": vid, "quantity_to_produce": 4,
    })
    assert create.status_code == 201
    bid = create.json()["id"]

    created_rows = await _logs_with_action(db_session, "production.batch_created")
    assert len(created_rows) == 1
    assert created_rows[0].new_values["quantity_to_produce"] == 4

    # First completion → audited. New contract requires good+damaged body.
    complete_body = {"good_quantity": 4, "damaged_quantity": 0}
    await client.patch(
        f"/api/v1/production/batches/{bid}/complete",
        json=complete_body, cookies=admin_cookies,
    )
    # Second completion → idempotent, no extra audit row.
    await client.patch(
        f"/api/v1/production/batches/{bid}/complete",
        json=complete_body, cookies=admin_cookies,
    )

    completed_rows = await _logs_with_action(db_session, "production.batch_completed")
    assert len(completed_rows) == 1
    assert completed_rows[0].new_values["good_quantity"] == 4
    assert completed_rows[0].new_values["damaged_quantity"] == 0


@pytest.mark.asyncio
async def test_report_generation_audited(
    client: AsyncClient, db_session: AsyncSession, admin_user, admin_cookies
):
    r = await client.get("/api/v1/reports/inventory?format=json", cookies=admin_cookies)
    assert r.status_code == 200
    rows = await _logs_with_action(db_session, "report.generated")
    assert len(rows) == 1
    assert rows[0].new_values["report"] == "inventory"
    assert rows[0].new_values["format"] == "json"

    r2 = await client.get("/api/v1/reports/inventory?format=csv", cookies=admin_cookies)
    assert r2.status_code == 200
    csv_rows = await _logs_with_action(db_session, "report.exported")
    assert any(row.new_values["report"] == "inventory" for row in csv_rows)
