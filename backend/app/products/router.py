import uuid
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_admin, require_authenticated
from app.exceptions import NotFoundException, ValidationException
from app.products import service, schemas
from app.products.schemas import CategoryCreate, CategoryUpdate, CategoryResponse
from app.storage.interface import get_storage_service, StorageService
from app.storage.minio_adapter import MinIOStorageService
from app.users.models import User, UserRole

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
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    cat = await service.create_category(db, **data.model_dump())
    return CategoryResponse.model_validate(cat)


@categories_router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    cat = await service.update_category(db, category_id, **data.model_dump(exclude_unset=True))
    return CategoryResponse.model_validate(cat)


@categories_router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_category(db, category_id)


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
    current_user: User = Depends(require_authenticated),
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
    current_user: User = Depends(require_authenticated),
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
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    dump = data.model_dump()
    variants = [v.model_dump() for v in data.variants]
    dump.pop("variants")
    product = await service.create_product(db, variants=variants, **dump)
    return schemas.ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int,
    data: schemas.ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    storage: StorageService = Depends(get_storage_service),
):
    product = await service.update_product(db, product_id, **data.model_dump(exclude_unset=True))
    response = schemas.ProductResponse.model_validate(product)
    return _populate_image_urls(response, storage)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_product(db, product_id)


# ── Variants ────────────────────────────────────────────

@router.post("/{product_id}/variants", response_model=schemas.VariantResponse, status_code=201)
async def create_variant(
    product_id: int,
    data: schemas.VariantCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    variant = await service.create_variant(db, product_id, **data.model_dump())
    return schemas.VariantResponse.model_validate(variant)


@router.patch("/variants/{variant_id}", response_model=schemas.VariantResponse)
async def update_variant(
    variant_id: int,
    data: schemas.VariantUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    variant = await service.update_variant(db, variant_id, admin_user_id=_admin.id, **data.model_dump(exclude_unset=True))
    return schemas.VariantResponse.model_validate(variant)


@router.delete("/variants/{variant_id}", status_code=204)
async def delete_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_variant(db, variant_id)


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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
):
    req = await service.update_product_size_requirement(db, req_id, data.quantity_per_item)
    return schemas.ProductSizeMaterialRequirementResponse.model_validate(req)


@router.delete("/{product_id}/size-requirements/{req_id}", status_code=204)
async def delete_size_requirement(
    product_id: int,
    req_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_product_size_requirement(db, req_id)


# ── Images ──────────────────────────────────────────────

@router.post("/{product_id}/images", response_model=schemas.ImageResponse, status_code=201)
async def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    is_primary: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
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
    """Stream a product image through the backend so the browser doesn't need
    direct network access to the MinIO sidecar. Public — the bucket policy is
    already public-read. Called by browsers via the Next.js /api/* rewrite."""
    if not isinstance(storage, MinIOStorageService):
        raise NotFoundException(detail="Image proxy only available for MinIO backend", code="proxy_unsupported")
    try:
        resp = storage.client.get_object(settings.minio_bucket, storage_key)
    except Exception:
        raise NotFoundException(detail="Image not found", code="image_not_found")
    try:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
    finally:
        resp.close()
        resp.release_conn()
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.patch("/images/{image_id}/primary", response_model=schemas.ImageResponse)
async def set_image_primary(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
):
    pm = await service.add_product_material(db, product_id, data.material_id, data.quantity_required, data.unit)
    return schemas.ProductMaterialResponse.model_validate(pm)


@router.delete("/materials/{pm_id}", status_code=204)
async def remove_material(
    pm_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_product_material(db, pm_id)
