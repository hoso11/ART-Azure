from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.customers.models import Customer
from app.exceptions import NotFoundException


async def get_customer_by_id(db: AsyncSession, customer_id: int) -> Customer:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundException(detail=f"Customer with id {customer_id} not found")
    return customer


async def list_customers(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
) -> tuple[list[Customer], int]:
    query = select(Customer)
    count_query = select(func.count()).select_from(Customer)

    if search:
        search_filter = Customer.name.ilike(f"%{search}%") | Customer.company_name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    sort_col = getattr(Customer, sort_by, Customer.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def create_customer(db: AsyncSession, **kwargs) -> Customer:
    customer = Customer(**kwargs)
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


async def update_customer(db: AsyncSession, customer_id: int, **kwargs) -> Customer:
    customer = await get_customer_by_id(db, customer_id)
    for key, value in kwargs.items():
        if value is not None:
            setattr(customer, key, value)
    await db.flush()
    await db.refresh(customer)
    return customer


async def delete_customer(db: AsyncSession, customer_id: int) -> None:
    customer = await get_customer_by_id(db, customer_id)
    customer.is_active = False
    await db.flush()
