import uuid
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import (
    require_admin,
    require_authenticated,
    require_roles,
    BUSINESS_MANAGER,
    PRODUCTS_VIEW,
)
from app.exceptions import NotFoundException, ValidationException
from app.products import service, schemas
from app.products.schemas import CategoryCreate, CategoryUpdate, CategoryResponse
from app.storage.interface import get_storage_service, StorageService
from app.users.models import User, UserRole
from app.activity import service as activity_service


def _product_snapshot(p) -> dict:
    return {
        "name": p.name,
        "sku": p.sku,
        "category_id": p.category_id,
        "description": p.description,
        "is_active": p.is_active,
    }


def _variant_snapshot(v) -> dict:
    return {
        "size": v.size,
        "color": v.color,
        "price": float(v.price) if v.price is not None else None,
        "stock_quantity": v.stock_quantity,
    }

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/products", tags=["Products"])
categories_router = APIRouter(prefix="/categories", tags=["Categories"])


# ── Helpers ────────────────────────────────────────────

def _populate_image_urls(response: schemas.ProductResponse, storage: StorageService) -> schemas.ProductResponse:
    """Fill the url field for every image so the browser can fetch through the
    backend (via the Next.js /api/* rewrite) rather than directly at the MinIO
    sidecar. MinIO's port is not publicly reachable in Azure — only the main
    container's WEBSITES_PORT is — so a direct MinIO URL on the browser fails
    silently and the card renders the placeholder. Proxying through
    /api/v1/products/images/file/<key> works in both local dev and Azure."""
    for image in response.images:
        if not image.url:
            image.url = f"/api/v1/products/images/file/{image.storage_key}"
    return response


def _populate_list_urls(response: schemas.ProductListResponse, storage: StorageService) -> schemas.ProductListResponse:
    for item in response.items:
        _populate_image_urls(item, storage)
    return response


def _apply_user_discount(response: schemas.ProductResponse, discount_percent: Decimal) -> schemas.ProductResponse:
    if not discount_percent or discount_percent <= 0:
        return response
    factor = (Decimal("100") - discount_percent) / Decimal("100")
    for variant in response.variants:
        variant.discounted_price = (variant.price * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return response


def _apply_list_discount(response: schemas.ProductListResponse, discount_percent: Decimal) -> schemas.ProductListResponse:
    for item in response.items:
        _apply_user_discount(item, discount_percent)
    return response


# ── Categories ──────────────────────────────────────────

@categories_router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
):
    cats = await service.list_categories(db)
    return [CategoryResponse.model_validate(c) for c in cats]


@categories_router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    cat = await service.create_category(db, **data.model_dump())
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="category.created", entity_type="category", entity_id=cat.id,
        new_values={"name": cat.name, "description": cat.description},
    )
    return CategoryResponse.model_validate(cat)


@categories_router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    cat = await service.update_category(db, category_id, **data.model_dump(exclude_unset=True))
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="category.updated", entity_type="category", entity_id=cat.id,
        new_values={"name": cat.name, "description": cat.description},
    )
    return CategoryResponse.model_validate(cat)


@categories_router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    await service.delete_category(db, category_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="category.deleted", entity_type="category", entity_id=category_id,
    )


# ── Products ────────────────────────────────────────────

@router.get("", response_model=schemas.ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    category_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTS_VIEW)),
    storage: StorageService = Depends(get_storage_service),
):
    products, total = await service.list_products(db, page, limit, sort_by, sort_order, search, category_id)
    response = schemas.ProductListResponse(
        items=[schemas.ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        limit=limit,
    )
    _populate_list_urls(response, storage)
    if current_user.role == UserRole.simple_user:
        _apply_list_discount(response, current_user.discount_percent)
    return response


@router.get("/public", response_model=schemas.ProductListResponse)
async def list_public_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    products, total = await service.list_products(
        db, page, limit, "created_at", "desc", None, category_id, active_only=True
    )
    response = schemas.ProductListResponse(
        items=[schemas.ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        limit=limit,
    )
    return _populate_list_urls(response, storage)


@router.get("/{product_id}", response_model=schemas.ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*PRODUCTS_VIEW)),
    storage: StorageService = Depends(get_storage_service),
):
    product = await service.get_product_by_id(db, product_id)
    response = schemas.ProductResponse.model_validate(product)
    _populate_image_urls(response, storage)
    if current_user.role == UserRole.simple_user:
        _apply_user_discount(response, current_user.discount_percent)
    return response


@router.post("", response_model=schemas.ProductResponse, status_code=201)
async def create_product(
    data: schemas.ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    dump = data.model_dump()
    variants = [v.model_dump() for v in data.variants]
    dump.pop("variants")
    product = await service.create_product(db, variants=variants, **dump)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="product.created", entity_type="product", entity_id=product.id,
        new_values={**_product_snapshot(product), "variant_count": len(product.variants or [])},
    )
    return schemas.ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int,
    data: schemas.ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
    storage: StorageService = Depends(get_storage_service),
):
    existing = await service.get_product_by_id(db, product_id)
    old_snapshot = _product_snapshot(existing)
    product = await service.update_product(db, product_id, **data.model_dump(exclude_unset=True))
    new_snapshot = _product_snapshot(product)
    if old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="product.updated", entity_type="product", entity_id=product.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )
    response = schemas.ProductResponse.model_validate(product)
    return _populate_image_urls(response, storage)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    existing = await service.get_product_by_id(db, product_id)
    snapshot = _product_snapshot(existing)
    await service.delete_product(db, product_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="product.deleted", entity_type="product", entity_id=product_id,
        old_values=snapshot,
        details=f"Deleted {snapshot['name']} ({snapshot['sku']})",
    )


# ── Variants ────────────────────────────────────────────

@router.post("/{product_id}/variants", response_model=schemas.VariantResponse, status_code=201)
async def create_variant(
    product_id: int,
    data: schemas.VariantCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    variant = await service.create_variant(db, product_id, **data.model_dump())
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="variant.created", entity_type="variant", entity_id=variant.id,
        new_values={"product_id": product_id, **_variant_snapshot(variant)},
    )
    return schemas.VariantResponse.model_validate(variant)


@router.patch("/variants/{variant_id}", response_model=schemas.VariantResponse)
async def update_variant(
    variant_id: int,
    data: schemas.VariantUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    from app.products.models import ProductVariant
    from sqlalchemy import select as _sel
    existing_q = await db.execute(_sel(ProductVariant).where(ProductVariant.id == variant_id))
    existing = existing_q.scalar_one_or_none()
    old_snapshot = _variant_snapshot(existing) if existing else None

    variant = await service.update_variant(db, variant_id, admin_user_id=admin.id, **data.model_dump(exclude_unset=True))
    new_snapshot = _variant_snapshot(variant)
    if old_snapshot and old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="variant.updated", entity_type="variant", entity_id=variant.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )
    return schemas.VariantResponse.model_validate(variant)


@router.delete("/variants/{variant_id}", status_code=204)
async def delete_variant(
    variant_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    from app.products.models import ProductVariant
    from sqlalchemy import select as _sel
    existing_q = await db.execute(_sel(ProductVariant).where(ProductVariant.id == variant_id))
    existing = existing_q.scalar_one_or_none()
    snapshot = _variant_snapshot(existing) if existing else None
    await service.delete_variant(db, variant_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="variant.deleted", entity_type="variant", entity_id=variant_id,
        old_values=snapshot,
    )


# ── Product Size Material Requirements ──────────────────
# Each row: which material + which size + qty per finished item.
# GET /products/{product_id}/size-requirements   → list all for the product
# POST /products/{product_id}/size-requirements  → add row
# PATCH /products/{product_id}/size-requirements/{req_id} → update qty
# DELETE /products/{product_id}/size-requirements/{req_id}

@router.get(
    "/{product_id}/size-requirements",
    response_model=list[schemas.ProductSizeMaterialRequirementResponse],
)
async def list_size_requirements(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    reqs = await service.list_product_size_requirements(db, product_id)
    return [schemas.ProductSizeMaterialRequirementResponse.model_validate(r) for r in reqs]


@router.post(
    "/{product_id}/size-requirements",
    response_model=schemas.ProductSizeMaterialRequirementResponse,
    status_code=201,
)
async def add_size_requirement(
    product_id: int,
    data: schemas.ProductSizeMaterialRequirementCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    req = await service.add_product_size_requirement(
        db, product_id, data.material_id, data.size, data.quantity_per_item
    )
    return schemas.ProductSizeMaterialRequirementResponse.model_validate(req)


@router.patch(
    "/{product_id}/size-requirements/{req_id}",
    response_model=schemas.ProductSizeMaterialRequirementResponse,
)
async def update_size_requirement(
    product_id: int,
    req_id: int,
    data: schemas.ProductSizeMaterialRequirementUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    req = await service.update_product_size_requirement(db, req_id, data.quantity_per_item)
    return schemas.ProductSizeMaterialRequirementResponse.model_validate(req)


@router.delete("/{product_id}/size-requirements/{req_id}", status_code=204)
async def delete_size_requirement(
    product_id: int,
    req_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    await service.delete_product_size_requirement(db, req_id)


# ── Images ──────────────────────────────────────────────

@router.post("/{product_id}/images", response_model=schemas.ImageResponse, status_code=201)
async def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    is_primary: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
    storage: StorageService = Depends(get_storage_service),
):
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationException(
            detail=f"Invalid image type '{content_type}'. Allowed: JPEG, PNG, WebP.",
            code="invalid_image_type",
        )

    contents = await file.read()

    # Validate file size
    if len(contents) > MAX_IMAGE_SIZE:
        raise ValidationException(
            detail=f"Image too large ({len(contents) // 1024}KB). Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB.",
            code="image_too_large",
        )

    # Use a unique key to avoid filename collisions
    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    key = f"products/{product_id}/{unique_name}"

    await storage.upload_file("art-images", key, contents, content_type)
    image = await service.add_product_image(db, product_id, key, is_primary)
    response = schemas.ImageResponse.model_validate(image)
    response.url = f"/api/v1/products/images/file/{key}"
    return response


@router.get("/images/file/{storage_key:path}")
async def stream_image_file(
    storage_key: str,
    storage: StorageService = Depends(get_storage_service),
):
    """Stream a product image through the backend. Backend-agnostic: works
    with either the MinIO local-dev sidecar (public-read bucket) or the
    Azure Blob private container in deployed envs. Called by browsers via
    the Next.js /api/* rewrite — never reaches the storage layer directly."""
    try:
        data, content_type = await storage.download_file(storage.bucket, storage_key)
    except Exception:
        raise NotFoundException(detail="Image not found", code="image_not_found")
    return Response(
        content=data,
        media_type=content_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.patch("/images/{image_id}/primary", response_model=schemas.ImageResponse)
async def set_image_primary(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
    storage: StorageService = Depends(get_storage_service),
):
    image = await service.set_image_primary(db, image_id)
    response = schemas.ImageResponse.model_validate(image)
    response.url = f"/api/v1/products/images/file/{image.storage_key}"
    return response


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
    storage: StorageService = Depends(get_storage_service),
):
    storage_key = await service.delete_product_image(db, image_id)
    await storage.delete_file("art-images", storage_key)


# ── Product Materials ───────────────────────────────────

@router.post("/{product_id}/materials", response_model=schemas.ProductMaterialResponse, status_code=201)
async def add_material(
    product_id: int,
    data: schemas.ProductMaterialCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    pm = await service.add_product_material(db, product_id, data.material_id, data.quantity_required, data.unit)
    return schemas.ProductMaterialResponse.model_validate(pm)


@router.delete("/materials/{pm_id}", status_code=204)
async def remove_material(
    pm_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    await service.delete_product_material(db, pm_id)
