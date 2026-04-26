from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.dependencies import require_admin
from app.reports import service
from app.users.models import User

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await service.get_dashboard_stats(db)


@router.get("/order-trends")
async def get_order_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await service.get_order_trends(db, days)


@router.get("/export/orders")
async def export_orders_csv(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    csv_content = await service.generate_orders_csv(db)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_report.csv"},
    )
