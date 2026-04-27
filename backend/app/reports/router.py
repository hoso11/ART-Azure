from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.dependencies import require_admin
from app.reports import service
from app.users.models import User

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Existing endpoints (unchanged) ──────────────────────

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


# ── New report endpoints ─────────────────────────────────

def _csv_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/orders")
async def get_orders_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: int | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_orders_report(db, start_date, end_date, status, customer_id)
    if format == "csv":
        return _csv_response(service.orders_report_to_csv(data), "orders_report.csv")
    return data


@router.get("/sales")
async def get_sales_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_sales_report(db, start_date, end_date)
    if format == "csv":
        return _csv_response(service.sales_report_to_csv(data), "sales_report.csv")
    return data


@router.get("/inventory")
async def get_inventory_report(
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_inventory_report(db)
    if format == "csv":
        return _csv_response(service.inventory_report_to_csv(data), "inventory_report.csv")
    return data


@router.get("/material-consumption")
async def get_material_consumption_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    material_id: int | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_material_consumption_report(db, start_date, end_date, material_id)
    if format == "csv":
        return _csv_response(service.material_consumption_to_csv(data), "material_consumption_report.csv")
    return data


@router.get("/production")
async def get_production_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    stage: str | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_production_report(db, start_date, end_date, stage)
    if format == "csv":
        return _csv_response(service.production_report_to_csv(data), "production_report.csv")
    return data


@router.get("/low-stock")
async def get_low_stock_report(
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_low_stock_report(db)
    if format == "csv":
        return _csv_response(service.low_stock_to_csv(data), "low_stock_report.csv")
    return data


@router.get("/customer-discounts")
async def get_customer_discount_report(
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    data = await service.get_customer_discount_report(db)
    if format == "csv":
        return _csv_response(service.customer_discount_to_csv(data), "customer_discount_report.csv")
    return data
