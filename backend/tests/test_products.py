import pytest
from httpx import AsyncClient

from app.main import app
from app.storage.interface import StorageService, get_storage_service


class FakeStorage(StorageService):
    """In-memory StorageService stub for tests — avoids touching MinIO/Azure."""

    bucket = "art-images"

    def __init__(self):
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    async def upload_file(self, bucket: str, key: str, file: bytes, content_type: str) -> str:
        self.objects[(bucket, key)] = (file, content_type)
        return key

    async def download_file(self, bucket: str, key: str) -> tuple[bytes, str]:
        if (bucket, key) not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[(bucket, key)]

    async def get_file_url(self, bucket: str, key: str) -> str:
        return f"/fake/{bucket}/{key}"

    async def delete_file(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)


@pytest.fixture
def fake_storage():
    storage = FakeStorage()
    app.dependency_overrides[get_storage_service] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_storage_service, None)


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


# ── Image gallery endpoints ─────────────────────────────


async def _create_product(client: AsyncClient, admin_cookies, sku: str) -> int:
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Image Host", "sku": sku},
        cookies=admin_cookies,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff"
    b"\xff?\x03\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_upload_image_returns_url_and_appears_on_product(
    client: AsyncClient, admin_user, admin_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-001")

    upload = await client.post(
        f"/api/v1/products/{product_id}/images?is_primary=true",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["is_primary"] is True
    assert body["storage_key"].startswith(f"products/{product_id}/")
    assert body["url"].endswith(body["storage_key"])

    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert get_resp.status_code == 200
    images = get_resp.json()["images"]
    assert len(images) == 1
    assert images[0]["url"] == f"/api/v1/products/images/file/{body['storage_key']}"


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_content_type(
    client: AsyncClient, admin_user, admin_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-002")

    resp = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("a.txt", b"not an image", "text/plain")},
        cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_image_type"


@pytest.mark.asyncio
async def test_set_primary_flips_existing_primary(
    client: AsyncClient, admin_user, admin_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-003")

    first = await client.post(
        f"/api/v1/products/{product_id}/images?is_primary=true",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    second = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("b.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    promote = await client.patch(
        f"/api/v1/products/images/{second_id}/primary", cookies=admin_cookies
    )
    assert promote.status_code == 200
    assert promote.json()["is_primary"] is True

    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    images = {img["id"]: img for img in get_resp.json()["images"]}
    assert images[second_id]["is_primary"] is True
    assert images[first_id]["is_primary"] is False


@pytest.mark.asyncio
async def test_delete_image_removes_db_row_and_storage_object(
    client: AsyncClient, admin_user, admin_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-004")

    upload = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    image_id = upload.json()["id"]
    storage_key = upload.json()["storage_key"]
    assert ("art-images", storage_key) in fake_storage.objects

    delete = await client.delete(
        f"/api/v1/products/images/{image_id}", cookies=admin_cookies
    )
    assert delete.status_code == 204
    assert ("art-images", storage_key) not in fake_storage.objects

    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert get_resp.json()["images"] == []


@pytest.mark.asyncio
async def test_image_proxy_streams_uploaded_bytes(
    client: AsyncClient, admin_user, admin_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-005")

    upload = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    assert upload.status_code == 201, upload.text
    storage_key = upload.json()["storage_key"]
    assert ("art-images", storage_key) in fake_storage.objects, list(fake_storage.objects.keys())

    resp = await client.get(f"/api/v1/products/images/file/{storage_key}")
    assert resp.status_code == 200, (resp.text, list(fake_storage.objects.keys()))
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content == PNG_BYTES


@pytest.mark.asyncio
async def test_image_proxy_404_for_missing_key(
    client: AsyncClient, fake_storage
):
    resp = await client.get("/api/v1/products/images/file/products/999/missing.png")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_simple_user_cannot_upload_image(
    client: AsyncClient, admin_user, admin_cookies, simple_user, user_cookies, fake_storage
):
    product_id = await _create_product(client, admin_cookies, "TST-IMG-006")

    resp = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=user_cookies,
    )
    assert resp.status_code == 403


# ── DELETE /products/variants/{id} — structured FK errors ───────────────────


async def _make_product_with_variant(client, admin_cookies, *, sku, stock=0):
    resp = await client.post("/api/v1/products", json={
        "name": f"VarDel {sku}",
        "sku": sku,
        "variants": [{"size": "M", "color": "Slate", "price": 10.00, "stock_quantity": stock}],
    }, cookies=admin_cookies)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["id"], body["variants"][0]["id"]


@pytest.mark.asyncio
async def test_delete_variant_no_references_succeeds(
    client: AsyncClient, admin_user, admin_cookies,
):
    """Fresh variant with no order_items or production_batches → 204."""
    _, variant_id = await _make_product_with_variant(client, admin_cookies, sku="VAR-DEL-OK-001")
    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_delete_variant_blocked_by_order_items(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """Variant referenced by order_items → 409 variant_has_orders, not 500."""
    _, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VAR-DEL-ORD-001", stock=10,
    )
    order_resp = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 2, "unit_price": 10.00}],
    }, cookies=admin_cookies)
    assert order_resp.status_code == 201

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}", cookies=admin_cookies,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "variant_has_orders"
    assert "1" in body["detail"]  # row count surfaces in the Armenian detail string


@pytest.mark.asyncio
async def test_delete_variant_blocked_by_production_batches(
    client: AsyncClient, admin_user, admin_cookies,
):
    """Variant referenced by a production_batch → 409 variant_has_production_batches."""
    from decimal import Decimal as _D
    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VAR-DEL-BAT-001",
    )
    # Need a material + size-requirement to create a batch.
    mat_resp = await client.post("/api/v1/inventory/materials", json={
        "name": "Var-batch mat", "sku": "MAT-VAR-BAT-001", "unit": "m",
        "quantity_on_hand": 50, "low_stock_threshold": 0,
    }, cookies=admin_cookies)
    mat_id = mat_resp.json()["id"]
    await client.post(
        f"/api/v1/products/{product_id}/size-requirements",
        json={"material_id": mat_id, "size": "M", "quantity_per_item": 1},
        cookies=admin_cookies,
    )
    batch_resp = await client.post("/api/v1/production/batches", json={
        "product_id": product_id, "variant_id": variant_id, "quantity_to_produce": 5,
    }, cookies=admin_cookies)
    assert batch_resp.status_code == 201, batch_resp.text

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}", cookies=admin_cookies,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "variant_has_production_batches"


@pytest.mark.asyncio
async def test_delete_variant_blocked_leaves_variant_intact(
    client: AsyncClient, admin_user, customer, admin_cookies,
):
    """A refused delete must not partially mutate state."""
    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VAR-DEL-INT-001", stock=5,
    )
    await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 1, "unit_price": 10.00}],
    }, cookies=admin_cookies)

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}", cookies=admin_cookies,
    )
    assert resp.status_code == 409

    # Variant still reachable on its parent product.
    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert get_resp.status_code == 200
    variant_ids = [v["id"] for v in get_resp.json()["variants"]]
    assert variant_id in variant_ids


@pytest.mark.asyncio
async def test_delete_variant_not_found_returns_404(
    client: AsyncClient, admin_user, admin_cookies,
):
    resp = await client.delete(
        "/api/v1/products/variants/999999", cookies=admin_cookies,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


# ── DELETE /products/{id}/force — admin force-delete ────────────────────────


async def _delete_all_variants(client, admin_cookies, product_id):
    """Strip a product down to zero variants by hard-deleting each in turn.
    Required because the create flow always seeds at least one variant."""
    p = (await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)).json()
    for v in p.get("variants", []):
        resp = await client.delete(
            f"/api/v1/products/variants/{v['id']}", cookies=admin_cookies,
        )
        assert resp.status_code == 204, resp.text


async def _force_delete_make_helper_user(db_session, role):
    from app.users.models import User
    from app.users.service import hash_password
    u = User(
        email=f"{role.value}@productforce.test.com",
        hashed_password=hash_password("Passw0rd!"),
        role=role,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


def _force_delete_cookies_for(user):
    from app.auth.service import create_access_token
    return {"access_token": create_access_token(user.id, user.role.value)}


@pytest.mark.asyncio
async def test_force_delete_product_zero_variants_succeeds(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session,
):
    """Product with zero variants, plus some metadata children → force OK.
    All four child tables are cleared via ORM cascade."""
    from app.products.models import (
        Product, ProductImage, ProductMaterial, ProductSizeMaterialRequirement,
    )
    from sqlalchemy import select as _sel

    product_id = await _create_product(client, admin_cookies, "FORCE-PROD-001")
    # Add an image, a recipe row, a size requirement.
    img_resp = await client.post(
        f"/api/v1/products/{product_id}/images",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        cookies=admin_cookies,
    )
    assert img_resp.status_code == 201, img_resp.text
    mat_resp = await client.post("/api/v1/inventory/materials", json={
        "name": "Force mat", "sku": "MAT-FORCE-PROD-001", "unit": "m",
        "quantity_on_hand": 10, "low_stock_threshold": 0,
    }, cookies=admin_cookies)
    mat_id = mat_resp.json()["id"]
    await client.post(
        f"/api/v1/products/{product_id}/size-requirements",
        json={"material_id": mat_id, "size": "M", "quantity_per_item": 1},
        cookies=admin_cookies,
    )

    # Strip variants so the gate passes.
    await _delete_all_variants(client, admin_cookies, product_id)

    resp = await client.delete(
        f"/api/v1/products/{product_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text

    # Product row gone.
    assert (await db_session.execute(
        _sel(Product).where(Product.id == product_id)
    )).scalar_one_or_none() is None

    # All metadata children cascade-removed.
    assert (await db_session.execute(
        _sel(ProductImage).where(ProductImage.product_id == product_id)
    )).scalars().all() == []
    assert (await db_session.execute(
        _sel(ProductSizeMaterialRequirement).where(
            ProductSizeMaterialRequirement.product_id == product_id
        )
    )).scalars().all() == []
    assert (await db_session.execute(
        _sel(ProductMaterial).where(ProductMaterial.product_id == product_id)
    )).scalars().all() == []


@pytest.mark.asyncio
async def test_force_delete_product_with_variants_refused(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Product with at least one variant → 422 product_has_variants."""
    product_id = await _create_product(client, admin_cookies, "FORCE-PROD-VAR")
    # The _create_product helper does not auto-seed variants; add one explicitly.
    v_resp = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": "M", "color": "Red", "price": 5.00},
        cookies=admin_cookies,
    )
    assert v_resp.status_code == 201, v_resp.text

    resp = await client.delete(
        f"/api/v1/products/{product_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "product_has_variants"


@pytest.mark.asyncio
async def test_force_delete_product_with_production_batches_refused(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session,
):
    """Defensive check: if a ProductionBatch row references this product
    despite the variants gate (the FK from batches.variant_id forces a
    valid variant somewhere, so we borrow one from a second product), the
    force-delete must refuse with product_has_production_batches."""
    from app.products.models import Product, ProductVariant
    from app.production.models import ProductionBatch
    from sqlalchemy import select as _sel

    # Product A: has zero variants (our target).
    target_id = await _create_product(client, admin_cookies, "FORCE-PROD-BATCH-A")
    # Product B: lends a valid variant_id to satisfy the batch FK.
    helper_id = await _create_product(client, admin_cookies, "FORCE-PROD-BATCH-B")
    v_resp = await client.post(
        f"/api/v1/products/{helper_id}/variants",
        json={"size": "M", "color": "Black", "price": 5.00},
        cookies=admin_cookies,
    )
    assert v_resp.status_code == 201, v_resp.text
    helper_variant_id = v_resp.json()["id"]

    # Insert a batch whose product_id points at the target but whose
    # variant_id points at the helper's variant — satisfies both FK
    # constraints while leaving the target's variant count at zero.
    batch = ProductionBatch(
        product_id=target_id,
        variant_id=helper_variant_id,
        quantity_to_produce=1,
        production_type="stock_based",
        current_stage="cutting",
        stage_status="completed",
        materials_deducted=True,
        stock_added=True,
        good_quantity=1,
        damaged_quantity=0,
        created_by=admin_user.id,
    )
    db_session.add(batch)
    await db_session.commit()

    # First gate passes (target has 0 variants), second gate fires.
    resp = await client.delete(
        f"/api/v1/products/{target_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "product_has_production_batches"

    # Target product row untouched.
    assert (await db_session.execute(
        _sel(Product).where(Product.id == target_id)
    )).scalar_one_or_none() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name",
    ["director", "production_manager", "warehouse_manager", "simple_user"],
)
async def test_force_delete_product_non_admin_forbidden(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session, role_name,
):
    from app.users.models import UserRole as _UR
    product_id = await _create_product(client, admin_cookies, f"FORCE-PROD-RBAC-{role_name[:5]}")
    await _delete_all_variants(client, admin_cookies, product_id)

    actor = await _force_delete_make_helper_user(db_session, _UR(role_name))
    actor_cookies = _force_delete_cookies_for(actor)
    resp = await client.delete(
        f"/api/v1/products/{product_id}/force", cookies=actor_cookies,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "insufficient_permissions"


@pytest.mark.asyncio
async def test_force_delete_product_writes_audit_row(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session,
):
    from app.activity.models import ActivityLog
    from sqlalchemy import func as _func, select as _sel

    product_id = await _create_product(client, admin_cookies, "FORCE-PROD-AUDIT")
    await _delete_all_variants(client, admin_cookies, product_id)

    before = (await db_session.execute(
        _sel(_func.count()).select_from(ActivityLog)
        .where(ActivityLog.action == "product.force_deleted")
    )).scalar() or 0
    resp = await client.delete(
        f"/api/v1/products/{product_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204
    rows = (await db_session.execute(
        _sel(ActivityLog).where(ActivityLog.action == "product.force_deleted")
    )).scalars().all()
    assert len(rows) - before == 1
    row = rows[-1]
    assert row.entity_type == "product"
    assert row.entity_id == product_id
    assert row.details and "Force deleted product" in row.details


@pytest.mark.asyncio
async def test_normal_product_delete_still_soft_deletes(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session,
):
    """Regression: existing DELETE /products/{id} keeps soft-delete semantics
    (sets is_active=False, row remains in the DB)."""
    from app.products.models import Product
    from sqlalchemy import select as _sel
    product_id = await _create_product(client, admin_cookies, "NORM-PROD-REG")
    resp = await client.delete(
        f"/api/v1/products/{product_id}", cookies=admin_cookies,
    )
    assert resp.status_code == 204
    # Row still present, just marked inactive.
    p = (await db_session.execute(
        _sel(Product).where(Product.id == product_id)
    )).scalar_one_or_none()
    assert p is not None
    assert p.is_active is False


# ── Variant usage counts on product detail ─────────────────────────────────


@pytest.mark.asyncio
async def test_variant_usage_counts_default_zero_when_no_references(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Fresh product with a fresh variant: both counts default to 0."""
    product_id = await _create_product(client, admin_cookies, "VAR-USE-001")
    v_resp = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": "M", "color": "Red", "price": 5.00},
        cookies=admin_cookies,
    )
    assert v_resp.status_code == 201

    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert len(body["variants"]) == 1
    assert body["variants"][0]["order_items_count"] == 0
    assert body["variants"][0]["production_batches_count"] == 0


@pytest.mark.asyncio
async def test_variant_usage_counts_reflect_order_and_batch_references(
    client: AsyncClient, admin_user, customer, admin_cookies, fake_storage, db_session,
):
    """One variant gets an order_item and a production_batch; another stays
    untouched. The detail endpoint must report 1/1 for the used variant and
    0/0 for the unused one."""
    from app.production.models import ProductionBatch

    product_id = await _create_product(client, admin_cookies, "VAR-USE-002")
    used = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": "M", "color": "Blue", "price": 10.00, "stock_quantity": 5},
        cookies=admin_cookies,
    )
    unused = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": "L", "color": "Green", "price": 10.00},
        cookies=admin_cookies,
    )
    used_id = used.json()["id"]
    unused_id = unused.json()["id"]

    # Order referencing the "used" variant.
    order = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": used_id, "quantity": 1, "unit_price": 10.00}],
    }, cookies=admin_cookies)
    assert order.status_code == 201

    # Production batch referencing the "used" variant.
    batch = ProductionBatch(
        product_id=product_id,
        variant_id=used_id,
        quantity_to_produce=1,
        production_type="stock_based",
        current_stage="cutting",
        stage_status="pending",
        materials_deducted=False,
        stock_added=False,
        created_by=admin_user.id,
    )
    db_session.add(batch)
    await db_session.commit()

    get_resp = await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)
    assert get_resp.status_code == 200
    variants = {v["id"]: v for v in get_resp.json()["variants"]}
    assert variants[used_id]["order_items_count"] == 1
    assert variants[used_id]["production_batches_count"] == 1
    assert variants[unused_id]["order_items_count"] == 0
    assert variants[unused_id]["production_batches_count"] == 0


@pytest.mark.asyncio
async def test_variant_usage_counts_not_populated_on_list_endpoint(
    client: AsyncClient, admin_user, customer, admin_cookies, fake_storage,
):
    """List endpoint deliberately skips the count computation. Variants in
    the list response carry the default 0 even when references exist."""
    product_id = await _create_product(client, admin_cookies, "VAR-USE-LIST")
    used = await client.post(
        f"/api/v1/products/{product_id}/variants",
        json={"size": "M", "color": "Black", "price": 5.00, "stock_quantity": 3},
        cookies=admin_cookies,
    )
    used_id = used.json()["id"]
    await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": used_id, "quantity": 1, "unit_price": 5.00}],
    }, cookies=admin_cookies)

    list_resp = await client.get("/api/v1/products", cookies=admin_cookies)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    target = next(p for p in items if p["id"] == product_id)
    target_variant = next(v for v in target["variants"] if v["id"] == used_id)
    # Default 0 on list — the field exists but is not computed there.
    assert target_variant["order_items_count"] == 0
    assert target_variant["production_batches_count"] == 0


# ── DELETE /products/variants/{id}/force — admin variant force-delete ────────


@pytest.mark.asyncio
async def test_force_delete_variant_no_references_succeeds(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Variant with no order_items or batches → 204 (and gone)."""
    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VFORCE-OK-001",
    )
    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text
    p = (await client.get(f"/api/v1/products/{product_id}", cookies=admin_cookies)).json()
    assert variant_id not in [v["id"] for v in p["variants"]]


@pytest.mark.asyncio
async def test_force_delete_variant_with_orders_snapshots_and_orphans(
    client: AsyncClient, admin_user, customer, admin_cookies, fake_storage,
):
    """Variant with an order referencing it → 204; order_item preserved
    with product_variant_id=NULL and snapshot fields populated."""
    from app.orders.models import OrderItem
    from sqlalchemy import select as _sel

    from tests.conftest import TestSessionLocal

    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VFORCE-ORD-001", stock=10,
    )
    order_resp = await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 2, "unit_price": 10.00}],
    }, cookies=admin_cookies)
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text

    async with TestSessionLocal() as session:
        items = (await session.execute(
            _sel(OrderItem).where(OrderItem.order_id == order_id)
        )).scalars().all()
        assert len(items) == 1
        item = items[0]
        assert item.product_variant_id is None
        assert item.variant_name_snapshot
        assert "M" in item.variant_name_snapshot
        assert item.product_name_snapshot
        # Quantity + price preserved for reports.
        assert item.quantity == 2
        assert float(item.unit_price) == 10.00


@pytest.mark.asyncio
async def test_force_delete_variant_with_batches_snapshots_and_orphans(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Variant with a production batch referencing it → 204; batch row
    preserved with variant_id=NULL and snapshot fields populated."""
    from app.production.models import ProductionBatch
    from sqlalchemy import select as _sel

    from tests.conftest import TestSessionLocal

    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VFORCE-BAT-001",
    )
    mat_resp = await client.post("/api/v1/inventory/materials", json={
        "name": "VForce mat", "sku": "MAT-VFORCE-001", "unit": "m",
        "quantity_on_hand": 50, "low_stock_threshold": 0,
    }, cookies=admin_cookies)
    mat_id = mat_resp.json()["id"]
    await client.post(
        f"/api/v1/products/{product_id}/size-requirements",
        json={"material_id": mat_id, "size": "M", "quantity_per_item": 1},
        cookies=admin_cookies,
    )
    batch_resp = await client.post("/api/v1/production/batches", json={
        "product_id": product_id, "variant_id": variant_id, "quantity_to_produce": 5,
    }, cookies=admin_cookies)
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text

    async with TestSessionLocal() as session:
        b = (await session.execute(
            _sel(ProductionBatch).where(ProductionBatch.id == batch_id)
        )).scalar_one()
        assert b.variant_id is None
        assert b.variant_name_snapshot
        assert b.product_name_snapshot


@pytest.mark.asyncio
async def test_force_delete_variant_writes_audit_row(
    client: AsyncClient, admin_user, customer, admin_cookies, fake_storage,
):
    """Force-delete must write a variant.force_deleted ActivityLog row
    with the snapshot and a non-empty details string."""
    from app.activity.models import ActivityLog
    from sqlalchemy import select as _sel

    from tests.conftest import TestSessionLocal

    product_id, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku="VFORCE-AUDIT-001", stock=5,
    )
    await client.post("/api/v1/orders", json={
        "customer_id": customer.id,
        "items": [{"product_variant_id": variant_id, "quantity": 1, "unit_price": 10.00}],
    }, cookies=admin_cookies)

    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        rows = (await session.execute(
            _sel(ActivityLog).where(ActivityLog.action == "variant.force_deleted")
        )).scalars().all()
        assert any(r.entity_id == variant_id for r in rows)
        row = next(r for r in rows if r.entity_id == variant_id)
        assert row.entity_type == "variant"
        assert row.details and "Force deleted variant" in row.details
        assert row.old_values  # snapshot present


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name",
    ["director", "production_manager", "warehouse_manager", "simple_user"],
)
async def test_force_delete_variant_non_admin_forbidden(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session, role_name,
):
    from app.users.models import UserRole as _UR
    _, variant_id = await _make_product_with_variant(
        client, admin_cookies, sku=f"VFORCE-RBAC-{role_name[:5]}",
    )
    actor = await _force_delete_make_helper_user(db_session, _UR(role_name))
    actor_cookies = _force_delete_cookies_for(actor)
    resp = await client.delete(
        f"/api/v1/products/variants/{variant_id}/force", cookies=actor_cookies,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "insufficient_permissions"


@pytest.mark.asyncio
async def test_force_delete_variant_not_found_returns_404(
    client: AsyncClient, admin_user, admin_cookies,
):
    resp = await client.delete(
        "/api/v1/products/variants/999999/force", cookies=admin_cookies,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


# ── DELETE /categories/{id} + /force — admin category force-delete (v48) ────


@pytest.mark.asyncio
async def test_list_categories_returns_product_count(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """GET /categories includes product_count per category — admin sees
    the blocker upfront before attempting a normal delete."""
    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Count-1", "description": "with products",
    }, cookies=admin_cookies)
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    empty_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Count-2", "description": "no products",
    }, cookies=admin_cookies)
    empty_id = empty_resp.json()["id"]

    await client.post("/api/v1/products", json={
        "name": "CatCountProd", "sku": "CAT-COUNT-001",
        "category_id": cat_id,
        "variants": [{"size": "M", "color": "Sky", "price": 5.00, "stock_quantity": 0}],
    }, cookies=admin_cookies)

    list_resp = await client.get("/api/v1/categories")
    assert list_resp.status_code == 200
    cats_by_id = {c["id"]: c for c in list_resp.json()}
    assert cats_by_id[cat_id]["product_count"] == 1
    assert cats_by_id[empty_id]["product_count"] == 0


@pytest.mark.asyncio
async def test_delete_category_blocked_by_products(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Normal delete refuses with typed 409 category_has_products."""
    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Del-Blocked", "description": "x",
    }, cookies=admin_cookies)
    cat_id = cat_resp.json()["id"]
    await client.post("/api/v1/products", json={
        "name": "BlockerProd", "sku": "CAT-BLK-001",
        "category_id": cat_id,
        "variants": [{"size": "M", "color": "Sky", "price": 5.00, "stock_quantity": 0}],
    }, cookies=admin_cookies)

    resp = await client.delete(f"/api/v1/categories/{cat_id}", cookies=admin_cookies)
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "category_has_products"
    # Count surfaces in the Armenian detail string.
    assert "1" in body["detail"]


@pytest.mark.asyncio
async def test_delete_empty_category_succeeds(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Category with zero products → normal delete works (existing behavior)."""
    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Del-OK", "description": "empty",
    }, cookies=admin_cookies)
    cat_id = cat_resp.json()["id"]
    resp = await client.delete(f"/api/v1/categories/{cat_id}", cookies=admin_cookies)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_force_delete_category_orphans_products(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    """Force delete sets product.category_id to NULL and removes the category;
    products survive intact with all metadata."""
    from app.products.models import Product, ProductCategory
    from sqlalchemy import select as _sel

    from tests.conftest import TestSessionLocal

    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Force-1", "description": "x",
    }, cookies=admin_cookies)
    cat_id = cat_resp.json()["id"]
    prod_resp = await client.post("/api/v1/products", json={
        "name": "ForceCatProd", "sku": "CAT-FORCE-001",
        "category_id": cat_id,
        "variants": [{"size": "M", "color": "Sky", "price": 5.00, "stock_quantity": 0}],
    }, cookies=admin_cookies)
    product_id = prod_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/categories/{cat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204, resp.text

    async with TestSessionLocal() as session:
        cat = (await session.execute(
            _sel(ProductCategory).where(ProductCategory.id == cat_id)
        )).scalar_one_or_none()
        assert cat is None, "category should be deleted"

        product = (await session.execute(
            _sel(Product).where(Product.id == product_id)
        )).scalar_one()
        assert product.category_id is None
        assert product.name == "ForceCatProd"
        assert product.sku == "CAT-FORCE-001"


@pytest.mark.asyncio
async def test_force_delete_category_writes_audit_row(
    client: AsyncClient, admin_user, admin_cookies, fake_storage,
):
    from app.activity.models import ActivityLog
    from sqlalchemy import select as _sel

    from tests.conftest import TestSessionLocal

    cat_resp = await client.post("/api/v1/categories", json={
        "name": "Cat-Audit", "description": "x",
    }, cookies=admin_cookies)
    cat_id = cat_resp.json()["id"]
    await client.post("/api/v1/products", json={
        "name": "AuditCatProd", "sku": "CAT-AUDIT-001",
        "category_id": cat_id,
        "variants": [{"size": "M", "color": "Sky", "price": 5.00, "stock_quantity": 0}],
    }, cookies=admin_cookies)

    resp = await client.delete(
        f"/api/v1/categories/{cat_id}/force", cookies=admin_cookies,
    )
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        rows = (await session.execute(
            _sel(ActivityLog).where(ActivityLog.action == "category.force_deleted")
        )).scalars().all()
        assert any(r.entity_id == cat_id for r in rows)
        row = next(r for r in rows if r.entity_id == cat_id)
        assert row.entity_type == "category"
        assert row.details and "Force deleted category" in row.details
        assert row.old_values["name"] == "Cat-Audit"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name",
    ["director", "production_manager", "warehouse_manager", "simple_user"],
)
async def test_force_delete_category_non_admin_forbidden(
    client: AsyncClient, admin_user, admin_cookies, fake_storage, db_session, role_name,
):
    from app.users.models import UserRole as _UR

    cat_resp = await client.post("/api/v1/categories", json={
        "name": f"Cat-RBAC-{role_name[:5]}", "description": "x",
    }, cookies=admin_cookies)
    cat_id = cat_resp.json()["id"]
    actor = await _force_delete_make_helper_user(db_session, _UR(role_name))
    actor_cookies = _force_delete_cookies_for(actor)
    resp = await client.delete(
        f"/api/v1/categories/{cat_id}/force", cookies=actor_cookies,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "insufficient_permissions"


@pytest.mark.asyncio
async def test_force_delete_category_not_found_returns_404(
    client: AsyncClient, admin_user, admin_cookies,
):
    resp = await client.delete(
        "/api/v1/categories/999999/force", cookies=admin_cookies,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
