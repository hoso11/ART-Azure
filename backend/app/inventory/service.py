from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.inventory.models import Material, Inventory, StockMovement
from app.exceptions import NotFoundException, ConflictException


# ── Materials ───────────────────────────────────────────

async def list_materials(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "name",
    sort_order: str = "asc",
    search: str | None = None,
) -> tuple[list[Material], int]:
    query = select(Material)
    count_query = select(func.count()).select_from(Material)

    if search:
        search_filter = Material.name.ilike(f"%{search}%") | Material.sku.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    sort_col = getattr(Material, sort_by, Material.name)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_material_by_id(db: AsyncSession, material_id: int) -> Material:
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise NotFoundException(detail=f"Material {material_id} not found")
    return material


async def create_material(db: AsyncSession, **kwargs) -> Material:
    existing = await db.execute(select(Material).where(Material.sku == kwargs.get("sku")))
    if existing.scalar_one_or_none():
        raise ConflictException(detail=f"Material with SKU {kwargs['sku']} already exists")

    material = Material(**kwargs)
    db.add(material)
    await db.flush()

    # Create inventory record
    inventory = Inventory(material_id=material.id, quantity_on_hand=Decimal("0"))
    db.add(inventory)
    await db.flush()
    await db.refresh(material)
    return material


async def update_material(db: AsyncSession, material_id: int, **kwargs) -> Material:
    material = await get_material_by_id(db, material_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(material, k, v)
    await db.flush()
    await db.refresh(material)
    return material


async def delete_material(db: AsyncSession, material_id: int) -> None:
    material = await get_material_by_id(db, material_id)
    await db.delete(material)
    await db.flush()


# ── Stock Movements ─────────────────────────────────────

async def create_stock_movement(
    db: AsyncSession,
    material_id: int,
    quantity_change: Decimal,
    reason: str,
    created_by: int,
    order_id: int | None = None,
) -> StockMovement:
    material = await get_material_by_id(db, material_id)

    # Update inventory
    if material.inventory:
        material.inventory.quantity_on_hand += quantity_change
    else:
        inv = Inventory(material_id=material_id, quantity_on_hand=quantity_change)
        db.add(inv)

    movement = StockMovement(
        material_id=material_id,
        quantity_change=quantity_change,
        reason=reason,
        created_by=created_by,
        order_id=order_id,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)

    # Check low stock threshold
    await db.refresh(material)
    if material.inventory and material.inventory.quantity_on_hand <= material.low_stock_threshold:
        logger.warning(
            "inventory.low_stock",
            material_id=material_id,
            material_name=material.name,
            quantity=float(material.inventory.quantity_on_hand),
            threshold=float(material.low_stock_threshold),
        )

    return movement


async def list_stock_movements(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    material_id: int | None = None,
) -> tuple[list[StockMovement], int]:
    query = select(StockMovement)
    count_query = select(func.count()).select_from(StockMovement)

    if material_id:
        query = query.where(StockMovement.material_id == material_id)
        count_query = count_query.where(StockMovement.material_id == material_id)

    sort_col = getattr(StockMovement, sort_by, StockMovement.created_at)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_low_stock_materials(db: AsyncSession) -> list[Material]:
    result = await db.execute(
        select(Material)
        .join(Inventory)
        .where(Inventory.quantity_on_hand <= Material.low_stock_threshold)
        .where(Material.low_stock_threshold > 0)
    )
    return list(result.scalars().all())
