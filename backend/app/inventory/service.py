from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from sqlalchemy.exc import IntegrityError

from app.inventory.models import Material, Inventory, StockMovement
from app.exceptions import NotFoundException, ConflictException, ValidationException


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

    initial_qty = Decimal(str(kwargs.pop("quantity_on_hand", 0)))
    material = Material(**kwargs)
    db.add(material)
    await db.flush()

    inventory = Inventory(material_id=material.id, quantity_on_hand=initial_qty)
    db.add(inventory)
    await db.flush()
    await db.refresh(material)
    return material


async def update_material(db: AsyncSession, material_id: int, admin_user_id: int | None = None, **kwargs) -> Material:
    material = await get_material_by_id(db, material_id)
    new_qty = kwargs.pop("quantity_on_hand", None)
    for k, v in kwargs.items():
        if v is not None:
            setattr(material, k, v)
    await db.flush()
    if new_qty is not None and admin_user_id is not None:
        current_qty = material.inventory.quantity_on_hand if material.inventory else Decimal("0")
        delta = Decimal(str(new_qty)) - current_qty
        if delta != 0:
            await create_stock_movement(db, material_id, delta, "adjustment", admin_user_id)
    await db.refresh(material)
    return material


async def delete_material(db: AsyncSession, material_id: int) -> None:
    material = await get_material_by_id(db, material_id)
    await db.delete(material)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflictException(
            detail="Cannot delete material: it is referenced by product size requirements",
            code="material_in_use",
        )


# ── Stock Movements ─────────────────────────────────────

async def create_stock_movement(
    db: AsyncSession,
    material_id: int,
    quantity_change: Decimal,
    reason: str,
    created_by: int,
    order_id: int | None = None,
    batch_id: int | None = None,
) -> StockMovement:
    material = await get_material_by_id(db, material_id)

    # Update inventory
    if material.inventory:
        new_qty = material.inventory.quantity_on_hand + quantity_change
        if new_qty < 0:
            raise ValidationException(
                detail=f"Insufficient stock: available {material.inventory.quantity_on_hand} {material.unit}, adjustment would result in {new_qty}",
                code="insufficient_stock",
            )
        material.inventory.quantity_on_hand = new_qty
    else:
        if quantity_change < 0:
            raise ValidationException(
                detail="Cannot apply negative adjustment: no inventory record exists",
                code="insufficient_stock",
            )
        inv = Inventory(material_id=material_id, quantity_on_hand=quantity_change)
        db.add(inv)

    movement = StockMovement(
        material_id=material_id,
        quantity_change=quantity_change,
        reason=reason,
        created_by=created_by,
        order_id=order_id,
        batch_id=batch_id,
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


async def force_delete_material(
    db: AsyncSession,
    material_id: int,
    *,
    admin_id: int,
) -> dict:
    """ADMIN ONLY. Hard-delete a Material AND its 1:1 Inventory row WITHOUT
    touching the inventory ledger. Reserved for materials whose
    `inventory.quantity_on_hand` is exactly zero.

    The Inventory row is a counter at zero by the time we reach this path,
    so removing it destroys no history. StockMovement rows are append-only
    audit and are NEVER deleted by this endpoint — if any exist, we refuse
    with a structured code so the admin sees exactly why.

    Refusal codes:
      material_quantity_not_zero    — inventory.quantity_on_hand != 0.
      material_has_stock_movements  — at least one StockMovement row
                                       references this material. Audit ledger
                                       preservation wins; the row stays.
      material_has_recipe_links     — at least one ProductMaterial or
                                       ProductSizeMaterialRequirement row
                                       references this material. Admin must
                                       clear the recipe linkage first via the
                                       existing endpoints.

    Returns: {"inventory_row_deleted": True, "stock_movements_preserved": 0,
              "recipe_links_preserved": 0} for the audit details string.
    """
    from app.products.models import ProductMaterial, ProductSizeMaterialRequirement

    material_result = await db.execute(
        select(Material).where(Material.id == material_id).with_for_update()
    )
    material = material_result.scalar_one_or_none()
    if material is None:
        raise NotFoundException(detail=f"Material {material_id} not found")

    inv_result = await db.execute(
        select(Inventory).where(Inventory.material_id == material_id).with_for_update()
    )
    inventory = inv_result.scalar_one_or_none()
    current_qty = inventory.quantity_on_hand if inventory else Decimal("0")
    if current_qty != 0:
        raise ValidationException(
            detail=(
                f"Հնարավոր չէ ուժով ջնջել: ընթացիկ քանակը {current_qty} {material.unit}. "
                "Քանակը պետք է լինի 0:"
            ),
            code="material_quantity_not_zero",
        )

    movement_count = (await db.execute(
        select(func.count()).select_from(StockMovement)
        .where(StockMovement.material_id == material_id)
    )).scalar() or 0
    if movement_count > 0:
        raise ValidationException(
            detail=(
                f"Հնարավոր չէ ուժով ջնջել: կան {movement_count} պահեստի շարժ: "
                "Պատմությունը պահպանվում է:"
            ),
            code="material_has_stock_movements",
        )

    pm_count = (await db.execute(
        select(func.count()).select_from(ProductMaterial)
        .where(ProductMaterial.material_id == material_id)
    )).scalar() or 0
    req_count = (await db.execute(
        select(func.count()).select_from(ProductSizeMaterialRequirement)
        .where(ProductSizeMaterialRequirement.material_id == material_id)
    )).scalar() or 0
    if pm_count + req_count > 0:
        raise ValidationException(
            detail=(
                f"Հնարավոր չէ ուժով ջնջել: կապված է {pm_count + req_count} բաղադրատոմսի հետ: "
                "Նախ հեռացրեք բաղադրատոմսի կապը:"
            ),
            code="material_has_recipe_links",
        )

    # All checks passed. Delete the Inventory row (counter at zero, not
    # history) then the Material row. Both inside the same transaction.
    inventory_row_deleted = False
    if inventory is not None:
        await db.delete(inventory)
        inventory_row_deleted = True
    await db.delete(material)
    await db.flush()

    summary = {
        "inventory_row_deleted": inventory_row_deleted,
        "stock_movements_preserved": 0,
        "recipe_links_preserved": 0,
    }
    logger.warning(
        "inventory.material_force_deleted",
        material_id=material_id,
        material_sku=material.sku,
        admin_id=admin_id,
        inventory_row_deleted=inventory_row_deleted,
    )
    return summary
