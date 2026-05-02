from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.dependencies import require_admin
from app.reports import service
from app.users.models import User
from app.activity import service as activity_service

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
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    csv_content = await service.generate_orders_csv(db)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="report.exported", entity_type="report",
        details="orders (legacy CSV export)",
        new_values={"report": "orders", "format": "csv"},
    )
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


async def _audit_report(
    db: AsyncSession,
    admin: User,
    request: Request,
    report: str,
    format: str,
    filters: dict | None = None,
):
    action = "report.exported" if format == "csv" else "report.generated"
    await activity_service.log_activity(
        db, user=admin, request=request,
        action=action, entity_type="report",
        new_values={"report": report, "format": format, "filters": filters or {}},
        details=report,
    )


@router.get("/orders")
async def get_orders_report(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: int | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_orders_report(db, start_date, end_date, status, customer_id)
    await _audit_report(db, admin, request, "orders", format, {
        "start_date": start_date, "end_date": end_date, "status": status, "customer_id": customer_id,
    })
    if format == "csv":
        return _csv_response(service.orders_report_to_csv(data), "orders_report.csv")
    return data


@router.get("/sales")
async def get_sales_report(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    customer_id: int | None = Query(None),
    order_id: int | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Sales / revenue report.

    Optional `customer_id` scopes the report (and CSV) to one customer; the
    response then includes a `selected_customer` block and `order_items` rows,
    and the CSV filename becomes
    `customer-report-<slug>-<YYYY-MM-DD>.csv`. Adding `order_id` further
    scopes to a single order belonging to that customer; the filename then
    becomes `customer-report-<slug>-order-<id>-<YYYY-MM-DD>.csv` and the
    response carries a `selected_order` block. `order_id` without
    `customer_id` returns 422.
    """
    from datetime import date
    data = await service.get_sales_report(db, start_date, end_date, customer_id, order_id)
    await _audit_report(db, admin, request, "sales", format, {
        "start_date": start_date, "end_date": end_date,
        "customer_id": customer_id, "order_id": order_id,
    })
    if format == "csv":
        if customer_id is not None and data.get("selected_customer"):
            slug = service.customer_filename_slug(
                data["selected_customer"]["name"], customer_id
            )
            today_iso = date.today().isoformat()
            if order_id is not None and data.get("selected_order"):
                filename = f"customer-report-{slug}-order-{order_id}-{today_iso}.csv"
            else:
                filename = f"customer-report-{slug}-{today_iso}.csv"
        else:
            filename = "sales_report.csv"
        return _csv_response(service.sales_report_to_csv(data), filename)
    return data


@router.get("/inventory")
async def get_inventory_report(
    request: Request,
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_inventory_report(db)
    await _audit_report(db, admin, request, "inventory", format)
    if format == "csv":
        return _csv_response(service.inventory_report_to_csv(data), "inventory_report.csv")
    return data


@router.get("/material-consumption")
async def get_material_consumption_report(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    material_id: int | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_material_consumption_report(db, start_date, end_date, material_id)
    await _audit_report(db, admin, request, "material_consumption", format, {
        "start_date": start_date, "end_date": end_date, "material_id": material_id,
    })
    if format == "csv":
        return _csv_response(service.material_consumption_to_csv(data), "material_consumption_report.csv")
    return data


@router.get("/production")
async def get_production_report(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    stage: str | None = Query(None),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_production_report(db, start_date, end_date, stage)
    await _audit_report(db, admin, request, "production", format, {
        "start_date": start_date, "end_date": end_date, "stage": stage,
    })
    if format == "csv":
        return _csv_response(service.production_report_to_csv(data), "production_report.csv")
    return data


@router.get("/low-stock")
async def get_low_stock_report(
    request: Request,
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_low_stock_report(db)
    await _audit_report(db, admin, request, "low_stock", format)
    if format == "csv":
        return _csv_response(service.low_stock_to_csv(data), "low_stock_report.csv")
    return data


@router.get("/customer-discounts")
async def get_customer_discount_report(
    request: Request,
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_customer_discount_report(db)
    await _audit_report(db, admin, request, "customer_discounts", format)
    if format == "csv":
        return _csv_response(service.customer_discount_to_csv(data), "customer_discount_report.csv")
    return data


@router.get("/damaged-stock")
async def get_damaged_stock_report(
    request: Request,
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await service.get_damaged_stock_report(db)
    await _audit_report(db, admin, request, "damaged_stock", format)
    if format == "csv":
        return _csv_response(service.damaged_stock_to_csv(data), "damaged_stock_report.csv")
    return data
