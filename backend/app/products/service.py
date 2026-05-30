from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.products.models import (
    Product, ProductVariant, ProductCategory, ProductImage,
    ProductMaterial, ProductSizeMaterialRequirement,
)
from app.exceptions import NotFoundException, ConflictException, ValidationException


# ── Categories ──────────────────────────────────────────

async def list_categories(db: AsyncSession) -> list[ProductCategory]:
    result = await db.execute(select(ProductCategory).order_by(ProductCategory.name))
    return list(result.scalars().all())


async def get_category_by_id(db: AsyncSession, category_id: int) -> ProductCategory:
    result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundException(detail=f"Category {category_id} not found")
    return cat


async def create_category(db: AsyncSession, name: str, description: str | None = None) -> ProductCategory:
    cat = ProductCategory(name=name, description=description)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def update_category(db: AsyncSession, category_id: int, **kwargs) -> ProductCategory:
    cat = await get_category_by_id(db, category_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(cat, k, v)
    await db.flush()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, category_id: int) -> None:
    cat = await get_category_by_id(db, category_id)
    await db.delete(cat)
    await db.flush()


# ── Products ────────────────────────────────────────────

async def list_products(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
    category_id: int | None = None,
    active_only: bool = False,
) -> tuple[list[Product], int]:
    query = select(Product).options(
        selectinload(Product.variants),
        selectinload(Product.images),
        selectinload(Product.category),
    )
    count_query = select(func.count()).select_from(Product)

    if search:
        search_filter = Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if category_id:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)

    if active_only:
        query = query.where(Product.is_active == True)
        count_query = count_query.where(Product.is_active == True)

    sort_col = getattr(Product, sort_by, Product.created_at)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().unique().all()), total


async def get_product_by_id(db: AsyncSession, product_id: int) -> Product:
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.materials),
        )
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise NotFoundException(detail=f"Product {product_id} not found")
    return product


async def create_product(db: AsyncSession, name: str, sku: str, variants: list = None, **kwargs) -> Product:
    existing = await db.execute(select(Product).where(Product.sku == sku))
    if existing.scalar_one_or_none():
        raise ConflictException(detail=f"Product with SKU {sku} already exists")

    product = Product(name=name, sku=sku, **kwargs)
    db.add(product)
    await db.flush()

    if variants:
        for v in variants:
            variant = ProductVariant(product_id=product.id, **v)
            db.add(variant)

    await db.flush()
    await db.refresh(product)
    return await get_product_by_id(db, product.id)


async def update_product(db: AsyncSession, product_id: int, **kwargs) -> Product:
    product = await get_product_by_id(db, product_id)
    for key, value in kwargs.items():
        if value is not None:
            setattr(product, key, value)
    await db.flush()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: int) -> None:
    product = await get_product_by_id(db, product_id)
    product.is_active = False
    await db.flush()


# ── Variants ────────────────────────────────────────────

async def create_variant(db: AsyncSession, product_id: int, **kwargs) -> ProductVariant:
    await get_product_by_id(db, product_id)
    variant = ProductVariant(product_id=product_id, **kwargs)
    db.add(variant)
    await db.flush()
    await db.refresh(variant)
    return variant


async def update_variant(db: AsyncSession, variant_id: int, admin_user_id: int = 0, **kwargs) -> ProductVariant:
    """Update variant fields. When stock_quantity increases, deducts materials from
    inventory based on ProductSizeMaterialRequirement rows matching this
    variant's (product_id, size). Validates all materials are sufficient before
    any deduction (all-or-nothing)."""
    from app.inventory.service import get_material_by_id, create_stock_movement
    from app.inventory.models import StockMovementReason

    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundException(detail=f"Variant {variant_id} not found")

    new_stock = kwargs.get("stock_quantity")
    if new_stock is not None:
        diff = int(new_stock) - int(variant.stock_quantity)
        if diff > 0:
            # Find size-specific material requirements for this product+size
            reqs_result = await db.execute(
                select(ProductSizeMaterialRequirement).where(
                    ProductSizeMaterialRequirement.product_id == variant.product_id,
                    ProductSizeMaterialRequirement.size == variant.size,
                )
            )
            size_reqs = list(reqs_result.scalars().all())

            if size_reqs:
                # Validate all materials first (fail-fast before touching inventory)
                for req in size_reqs:
                    material = await get_material_by_id(db, req.material_id)
                    needed = Decimal(str(diff)) * req.quantity_per_item
                    available = material.inventory.quantity_on_hand if material.inventory else Decimal("0")
                    if available < needed:
                        raise ValidationException(
                            detail=(
                                f"Insufficient stock for '{material.name}': "
                                f"need {needed} {material.unit}, have {available}"
                            ),
                            code="insufficient_material",
                        )
                # All checks passed — deduct
                for req in size_reqs:
                    deduction = -(Decimal(str(diff)) * req.quantity_per_item)
                    await create_stock_movement(
                        db, req.material_id, deduction,
                        StockMovementReason.production_usage, admin_user_id,
                    )

    for k, v in kwargs.items():
        if v is not None:
            setattr(variant, k, v)
    await db.flush()
    await db.refresh(variant)
    return variant


async def delete_variant(db: AsyncSession, variant_id: int) -> None:
    """Delete a ProductVariant.

    Pre-flight checks the two FK referrers that block the underlying SQL
    DELETE and surface as opaque IntegrityError → uncaught 500 today:

      * order_items.product_variant_id  → 409 variant_has_orders
      * production_batches.variant_id   → 409 variant_has_production_batches

    Both checks return a typed ConflictException with a `details` payload
    that includes the row count, so the frontend can render a real reason
    instead of the silent failure path documented in the v40 handoff.

    A defensive `IntegrityError` catch wraps the actual delete so that any
    future FK referrer also produces a structured 409 instead of a 500.
    """
    from sqlalchemy.exc import IntegrityError
    from app.orders.models import OrderItem
    from app.production.models import ProductionBatch

    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundException(detail=f"Variant {variant_id} not found")

    order_item_count = (await db.execute(
        select(func.count()).select_from(OrderItem)
        .where(OrderItem.product_variant_id == variant_id)
    )).scalar() or 0
    if order_item_count > 0:
        raise ConflictException(
            detail=(
                f"Հնարավոր չէ ջնջել. տարբերակը կապված է {order_item_count} պատվերի տողի հետ:"
            ),
            code="variant_has_orders",
        )

    batch_count = (await db.execute(
        select(func.count()).select_from(ProductionBatch)
        .where(ProductionBatch.variant_id == variant_id)
    )).scalar() or 0
    if batch_count > 0:
        raise ConflictException(
            detail=(
                f"Հնարավոր չէ ջնջել. տարբերակը կապված է {batch_count} արտադրության հետ:"
            ),
            code="variant_has_production_batches",
        )

    await db.delete(variant)
    try:
        await db.flush()
    except IntegrityError:
        # Defensive — if a future FK referrer lands without an updated
        # pre-flight, the user sees a structured 409 instead of a 500.
        raise ConflictException(
            detail="Հնարավոր չէ ջնջել. տարբերակը կապակցված է այլ գրառումների հետ:",
            code="variant_in_use",
        )


# ── Images ──────────────────────────────────────────────

async def add_product_image(db: AsyncSession, product_id: int, storage_key: str, is_primary: bool = False) -> ProductImage:
    await get_product_by_id(db, product_id)
    if is_primary:
        existing = await db.execute(
            select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.is_primary == True)
        )
        for img in existing.scalars().all():
            img.is_primary = False

    image = ProductImage(product_id=product_id, storage_key=storage_key, is_primary=is_primary)
    db.add(image)
    await db.flush()
    await db.refresh(image)
    return image


async def set_image_primary(db: AsyncSession, image_id: int) -> ProductImage:
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise NotFoundException(detail=f"Image {image_id} not found")
    existing = await db.execute(
        select(ProductImage).where(ProductImage.product_id == image.product_id, ProductImage.is_primary == True)
    )
    for img in existing.scalars().all():
        img.is_primary = False
    image.is_primary = True
    await db.flush()
    await db.refresh(image)
    return image


async def delete_product_image(db: AsyncSession, image_id: int) -> str:
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise NotFoundException(detail=f"Image {image_id} not found")
    storage_key = image.storage_key
    await db.delete(image)
    await db.flush()
    return storage_key


# ── Product Materials ───────────────────────────────────

async def add_product_material(db: AsyncSession, product_id: int, material_id: int, quantity_required, unit: str) -> ProductMaterial:
    await get_product_by_id(db, product_id)
    from app.inventory.models import Material as InventoryMaterial
    mat = await db.execute(select(InventoryMaterial).where(InventoryMaterial.id == material_id))
    if not mat.scalar_one_or_none():
        raise NotFoundException(detail=f"Material {material_id} not found")
    pm = ProductMaterial(product_id=product_id, material_id=material_id, quantity_required=quantity_required, unit=unit)
    db.add(pm)
    await db.flush()
    await db.refresh(pm)
    return pm


async def delete_product_material(db: AsyncSession, pm_id: int) -> None:
    result = await db.execute(select(ProductMaterial).where(ProductMaterial.id == pm_id))
    pm = result.scalar_one_or_none()
    if not pm:
        raise NotFoundException(detail=f"ProductMaterial {pm_id} not found")
    await db.delete(pm)
    await db.flush()


# ── Product Size Material Requirements ──────────────────
# Each row = which material, which size, how much per finished item.
# Used to auto-deduct inventory when a variant's stock_quantity rises.

async def list_product_size_requirements(
    db: AsyncSession, product_id: int
) -> list[ProductSizeMaterialRequirement]:
    result = await db.execute(
        select(ProductSizeMaterialRequirement)
        .where(ProductSizeMaterialRequirement.product_id == product_id)
        .order_by(ProductSizeMaterialRequirement.size, ProductSizeMaterialRequirement.material_id)
    )
    return list(result.scalars().all())


async def add_product_size_requirement(
    db: AsyncSession, product_id: int, material_id: int, size: str, quantity_per_item: Decimal
) -> ProductSizeMaterialRequirement:
    from app.inventory.models import Material as InventoryMaterial
    mat = await db.execute(select(InventoryMaterial).where(InventoryMaterial.id == material_id))
    if not mat.scalar_one_or_none():
        raise NotFoundException(detail=f"Material {material_id} not found")
    existing = await db.execute(
        select(ProductSizeMaterialRequirement).where(
            ProductSizeMaterialRequirement.product_id == product_id,
            ProductSizeMaterialRequirement.material_id == material_id,
            ProductSizeMaterialRequirement.size == size,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(detail=f"Requirement for this material+size already exists")

    req = ProductSizeMaterialRequirement(
        product_id=product_id,
        material_id=material_id,
        size=size,
        quantity_per_item=quantity_per_item,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def update_product_size_requirement(
    db: AsyncSession, req_id: int, quantity_per_item: Decimal
) -> ProductSizeMaterialRequirement:
    result = await db.execute(
        select(ProductSizeMaterialRequirement).where(ProductSizeMaterialRequirement.id == req_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise NotFoundException(detail=f"Requirement {req_id} not found")
    req.quantity_per_item = quantity_per_item
    await db.flush()
    await db.refresh(req)
    return req


async def delete_product_size_requirement(db: AsyncSession, req_id: int) -> None:
    result = await db.execute(
        select(ProductSizeMaterialRequirement).where(ProductSizeMaterialRequirement.id == req_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise NotFoundException(detail=f"Requirement {req_id} not found")
    await db.delete(req)
    await db.flush()
