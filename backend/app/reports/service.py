import csv
import io
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.orders.models import Order, OrderStatus
from app.inventory.models import Material, Inventory
from app.production.models import ProductionStage, StageStatus
from app.activity.models import ActivityLog


async def get_dashboard_stats(db: AsyncSession) -> dict:
    # Active orders
    active_orders = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.status.in_([OrderStatus.confirmed, OrderStatus.in_production])
        )
    )

    # Delayed orders
    delayed_orders = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.deadline < datetime.utcnow(),
            Order.status.not_in([OrderStatus.shipped, OrderStatus.cancelled, OrderStatus.completed]),
        )
    )

    # Low stock materials
    low_stock = await db.execute(
        select(func.count())
        .select_from(Material)
        .join(Inventory)
        .where(Inventory.quantity_on_hand <= Material.low_stock_threshold)
        .where(Material.low_stock_threshold > 0)
    )

    # Production stage summary
    stage_summary = await db.execute(
        select(ProductionStage.status, func.count())
        .group_by(ProductionStage.status)
    )

    # Recent activity
    recent = await db.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
    )

    return {
        "active_orders": active_orders.scalar(),
        "delayed_orders": delayed_orders.scalar(),
        "low_stock_items": low_stock.scalar(),
        "production_summary": {row[0].value: row[1] for row in stage_summary.all()},
        "recent_activity": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "created_at": a.created_at.isoformat(),
            }
            for a in recent.scalars().all()
        ],
    }


async def get_order_trends(db: AsyncSession, days: int = 30) -> list[dict]:
    start_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Order.created_at).label("date"),
            func.count().label("count"),
        )
        .where(Order.created_at >= start_date)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )
    return [{"date": str(row.date), "count": row.count} for row in result.all()]


async def generate_orders_csv(db: AsyncSession) -> str:
    result = await db.execute(select(Order).order_by(Order.created_at.desc()))
    orders = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Customer ID", "Status", "Priority", "Deadline", "Created At"])
    for order in orders:
        writer.writerow([
            order.id,
            order.customer_id,
            order.status.value,
            order.priority.value,
            order.deadline.isoformat() if order.deadline else "",
            order.created_at.isoformat(),
        ])
    return output.getvalue()
