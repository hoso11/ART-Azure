import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.orders.models import Order, OrderItem, OrderStatus
from app.inventory.models import Material, Inventory, StockMovement
from app.production.models import ProductionStage
from app.activity.models import ActivityLog
from app.exceptions import ValidationException


# ── Helpers ─────────────────────────────────────────────

def _parse_dates(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    start = end = None
    try:
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError as exc:
        raise ValidationException(
            detail=f"Invalid date format '{exc}'. Use YYYY-MM-DD.",
            code="invalid_date",
        )
    return start, end


def _to_csv(headers: list[str], rows: list[list]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


# ── Existing endpoints (unchanged) ──────────────────────

async def get_dashboard_stats(db: AsyncSession) -> dict:
    active_orders = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.status.in_([OrderStatus.confirmed, OrderStatus.in_production])
        )
    )
    delayed_orders = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.deadline < datetime.utcnow(),
            Order.status.not_in([OrderStatus.shipped, OrderStatus.cancelled, OrderStatus.completed]),
        )
    )
    low_stock = await db.execute(
        select(func.count())
        .select_from(Material)
        .join(Inventory)
        .where(Inventory.quantity_on_hand <= Material.low_stock_threshold)
        .where(Material.low_stock_threshold > 0)
    )
    stage_summary = await db.execute(
        select(ProductionStage.status, func.count())
        .group_by(ProductionStage.status)
    )
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


# ── Orders Report ────────────────────────────────────────

async def get_orders_report(
    db: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
) -> list[dict]:
    start, end = _parse_dates(start_date, end_date)
    query = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .order_by(Order.created_at.desc())
    )
    if start:
        query = query.where(Order.created_at >= start)
    if end:
        query = query.where(Order.created_at <= end)
    if status:
        query = query.where(Order.status == status)
    if customer_id:
        query = query.where(Order.customer_id == customer_id)

    result = await db.execute(query)
    orders = result.scalars().unique().all()

    rows = []
    for o in orders:
        total = sum(Decimal(str(item.unit_price)) * item.quantity for item in o.items)
        rows.append({
            "id": o.id,
            "customer_name": o.customer.name if o.customer else "",
            "company_name": o.customer.company_name if o.customer else None,
            "status": o.status.value,
            "priority": o.priority.value,
            "total_price": float(total),
            "created_at": o.created_at.isoformat(),
            "deadline": o.deadline.isoformat() if o.deadline else None,
            "updated_at": o.updated_at.isoformat(),
        })
    return rows


def orders_report_to_csv(data: list[dict]) -> str:
    headers = ["ID", "Customer", "Company", "Status", "Priority", "Total Price", "Created At", "Deadline", "Updated At"]
    rows = [
        [
            r["id"], r["customer_name"], r["company_name"] or "",
            r["status"], r["priority"], r["total_price"],
            r["created_at"], r["deadline"] or "", r["updated_at"],
        ]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Sales / Revenue Report ───────────────────────────────

async def get_sales_report(
    db: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    customer_id: int | None = None,
    order_id: int | None = None,
) -> dict:
    """Sales / revenue summary.

    When `customer_id` is provided, the report is scoped to a single customer:
    summary, by_day, and by_customer all reflect only that customer's orders,
    and the response also carries `selected_customer` metadata plus a
    per-OrderItem `order_items` list for the filtered, revenue-eligible
    orders. The customer must exist (404 otherwise).

    `order_id` further narrows the report to a single order belonging to
    `customer_id`. It is invalid without `customer_id` (422
    `order_id_requires_customer_id`); 404 `order_not_found` if missing; 422
    `order_not_for_customer` if it belongs to a different customer. The
    response then carries a `selected_order` block.

    When `customer_id` is None, behavior is preserved bit-for-bit:
    `selected_customer` is None and `order_items` is an empty list, so the
    CSV writer's new sections produce no output.
    """
    from app.customers.models import Customer
    from app.exceptions import NotFoundException

    if order_id is not None and customer_id is None:
        raise ValidationException(
            detail="order_id requires customer_id",
            code="order_id_requires_customer_id",
        )

    start, end = _parse_dates(start_date, end_date)

    selected_customer: dict | None = None
    if customer_id is not None:
        cust_result = await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        customer_row = cust_result.scalar_one_or_none()
        if customer_row is None:
            raise NotFoundException(
                detail=f"Customer {customer_id} not found",
                code="customer_not_found",
            )
        selected_customer = {
            "id": customer_row.id,
            "name": customer_row.name,
            "company_name": customer_row.company_name,
        }

    selected_order: dict | None = None
    if order_id is not None:
        order_lookup = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order_row = order_lookup.scalar_one_or_none()
        if order_row is None:
            raise NotFoundException(
                detail=f"Order {order_id} not found",
                code="order_not_found",
            )
        if order_row.customer_id != customer_id:
            raise ValidationException(
                detail=f"Order {order_id} does not belong to customer {customer_id}",
                code="order_not_for_customer",
            )
        selected_order = {
            "id": order_row.id,
            "order_date": order_row.created_at.date().isoformat(),
            "status": order_row.status.value,
        }

    query = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product_variant),
            selectinload(Order.customer),
        )
    )
    if start:
        query = query.where(Order.created_at >= start)
    if end:
        query = query.where(Order.created_at <= end)
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
    if order_id is not None:
        query = query.where(Order.id == order_id)

    result = await db.execute(query)
    orders = result.scalars().unique().all()

    revenue_statuses = {
        OrderStatus.confirmed, OrderStatus.in_production,
        OrderStatus.completed, OrderStatus.shipped,
    }
    confirmed_count = sum(1 for o in orders if o.status == OrderStatus.confirmed)
    completed_count = sum(1 for o in orders if o.status == OrderStatus.completed)

    total_revenue = Decimal("0")
    by_day: dict[str, dict] = {}
    by_customer: dict[int, dict] = {}
    order_items: list[dict] = []

    # Resolve product names for items in revenue-eligible orders only when
    # we're going to include them (i.e. customer_id is set). Single batched
    # fetch; avoids N+1 lazy loads on ProductVariant.product.
    if customer_id is not None:
        from app.products.models import Product
        product_ids = {
            item.product_variant.product_id
            for o in orders if o.status in revenue_statuses
            for item in o.items if item.product_variant is not None
        }
        product_map: dict[int, Product] = {}
        if product_ids:
            prod_result = await db.execute(
                select(Product).where(Product.id.in_(product_ids))
            )
            product_map = {p.id: p for p in prod_result.scalars().all()}
    else:
        product_map = {}

    for o in orders:
        order_total = sum(Decimal(str(i.unit_price)) * i.quantity for i in o.items)
        if o.status not in revenue_statuses:
            continue

        total_revenue += order_total
        date_key = o.created_at.date().isoformat()
        by_day.setdefault(date_key, {"date": date_key, "count": 0, "revenue": Decimal("0")})
        by_day[date_key]["count"] += 1
        by_day[date_key]["revenue"] += order_total

        cid = o.customer_id
        by_customer.setdefault(cid, {
            "customer_name": o.customer.name if o.customer else f"Customer #{cid}",
            "company_name": o.customer.company_name if o.customer else None,
            "orders": 0,
            "revenue": Decimal("0"),
        })
        by_customer[cid]["orders"] += 1
        by_customer[cid]["revenue"] += order_total

        if customer_id is not None:
            for item in o.items:
                variant = item.product_variant
                product = product_map.get(variant.product_id) if variant else None
                unit_price = Decimal(str(item.unit_price))
                line_total = unit_price * item.quantity
                order_items.append({
                    "order_id": o.id,
                    "order_date": o.created_at.date().isoformat(),
                    "product_name": product.name if product else "",
                    "sku": product.sku if product else "",
                    "size": variant.size if variant else "",
                    "color": variant.color if variant else "",
                    "quantity": item.quantity,
                    "unit_price": float(unit_price),
                    "total_price": float(line_total),
                })

    return {
        "selected_customer": selected_customer,
        "selected_order": selected_order,
        "summary": {
            "total_orders": len(orders),
            "confirmed_orders": confirmed_count,
            "completed_orders": completed_count,
            "total_revenue": float(total_revenue),
        },
        "by_day": [
            {"date": v["date"], "count": v["count"], "revenue": float(v["revenue"])}
            for v in sorted(by_day.values(), key=lambda x: x["date"])
        ],
        "by_customer": [
            {
                "customer_name": v["customer_name"],
                "company_name": v["company_name"],
                "orders": v["orders"],
                "revenue": float(v["revenue"]),
            }
            for v in sorted(by_customer.values(), key=lambda x: -float(x["revenue"]))
        ],
        "order_items": order_items,
    }


_SLUG_KEEP = "abcdefghijklmnopqrstuvwxyz0123456789-_"


def customer_filename_slug(name: str | None, customer_id: int) -> str:
    """ASCII-safe slug for use in Content-Disposition filenames.

    Preserves lowercase letters, digits, dash, underscore. Spaces become
    dashes. Non-ASCII characters (incl. Armenian) are dropped. If the
    cleaned slug is empty, falls back to ``customer-{id}``.
    """
    if not name:
        return f"customer-{customer_id}"
    lowered = name.strip().lower().replace(" ", "-")
    cleaned = "".join(ch for ch in lowered if ch in _SLUG_KEEP)
    # Collapse repeated dashes, strip leading/trailing dashes.
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-_")
    return cleaned or f"customer-{customer_id}"


def sales_report_to_csv(data: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    selected = data.get("selected_customer")
    if selected:
        writer.writerow(["Selected Customer"])
        writer.writerow(["Customer", "Company", "ID"])
        writer.writerow([
            selected["name"],
            selected.get("company_name") or "",
            selected["id"],
        ])
        writer.writerow([])

    selected_o = data.get("selected_order")
    if selected_o:
        writer.writerow(["Selected Order"])
        writer.writerow(["Order ID", "Order Date", "Status"])
        writer.writerow([
            selected_o["id"],
            selected_o["order_date"],
            selected_o["status"],
        ])
        writer.writerow([])

    s = data["summary"]
    writer.writerow(["Sales Report Summary"])
    writer.writerow(["Total Orders", s["total_orders"]])
    writer.writerow(["Confirmed Orders", s["confirmed_orders"]])
    writer.writerow(["Completed Orders", s["completed_orders"]])
    writer.writerow(["Total Revenue", s["total_revenue"]])
    writer.writerow([])
    writer.writerow(["Revenue by Day", "Order Count", "Revenue"])
    for row in data["by_day"]:
        writer.writerow([row["date"], row["count"], row["revenue"]])
    writer.writerow([])
    writer.writerow(["Customer", "Company", "Orders", "Revenue"])
    for row in data["by_customer"]:
        writer.writerow([row["customer_name"], row["company_name"] or "", row["orders"], row["revenue"]])

    items = data.get("order_items") or []
    if items:
        writer.writerow([])
        writer.writerow(["Order Items"])
        writer.writerow([
            "Order ID", "Order Date", "Product", "SKU",
            "Size", "Color", "Quantity", "Unit Price", "Total Price",
        ])
        for r in items:
            writer.writerow([
                r["order_id"], r["order_date"], r["product_name"], r["sku"],
                r["size"], r["color"], r["quantity"],
                r["unit_price"], r["total_price"],
            ])
    return output.getvalue()


# ── Inventory / Stock Report ─────────────────────────────

async def get_inventory_report(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Material).order_by(Material.name))
    materials = result.scalars().all()

    rows = []
    for m in materials:
        qty = m.inventory.quantity_on_hand if m.inventory else Decimal("0")
        threshold = m.low_stock_threshold
        rows.append({
            "id": m.id,
            "name": m.name,
            "sku": m.sku,
            "unit": m.unit,
            "quantity_on_hand": float(qty),
            "low_stock_threshold": float(threshold),
            "is_low_stock": threshold > 0 and qty <= threshold,
        })
    return rows


def inventory_report_to_csv(data: list[dict]) -> str:
    headers = ["ID", "Material", "SKU", "Unit", "Available Qty", "Min Qty", "Low Stock"]
    rows = [
        [r["id"], r["name"], r["sku"], r["unit"],
         r["quantity_on_hand"], r["low_stock_threshold"],
         "Yes" if r["is_low_stock"] else "No"]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Material Consumption Report ──────────────────────────

async def get_material_consumption_report(
    db: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    material_id: int | None = None,
) -> list[dict]:
    from app.users.models import User

    start, end = _parse_dates(start_date, end_date)
    query = select(StockMovement).order_by(StockMovement.created_at.desc())
    if start:
        query = query.where(StockMovement.created_at >= start)
    if end:
        query = query.where(StockMovement.created_at <= end)
    if material_id:
        query = query.where(StockMovement.material_id == material_id)

    result = await db.execute(query)
    movements = result.scalars().all()

    user_ids = list({m.created_by for m in movements})
    users_map: dict[int, str] = {}
    if user_ids:
        u_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_map = {u.id: u.email for u in u_result.scalars().all()}

    return [
        {
            "id": m.id,
            "material_name": m.material.name if m.material else f"Material #{m.material_id}",
            "unit": m.material.unit if m.material else "",
            "quantity_change": float(m.quantity_change),
            "order_id": m.order_id,
            "reason": m.reason.value,
            "created_at": m.created_at.isoformat(),
            "created_by_email": users_map.get(m.created_by, f"User #{m.created_by}"),
        }
        for m in movements
    ]


def material_consumption_to_csv(data: list[dict]) -> str:
    headers = ["ID", "Material", "Unit", "Qty Change", "Order ID", "Reason", "Date", "Admin"]
    rows = [
        [r["id"], r["material_name"], r["unit"], r["quantity_change"],
         r["order_id"] or "", r["reason"], r["created_at"], r["created_by_email"]]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Production Status Report ─────────────────────────────

async def get_production_report(
    db: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    stage: str | None = None,
) -> list[dict]:
    start, end = _parse_dates(start_date, end_date)
    query = select(ProductionStage).order_by(ProductionStage.order_id)

    if start or end:
        order_subq = select(Order.id)
        if start:
            order_subq = order_subq.where(Order.created_at >= start)
        if end:
            order_subq = order_subq.where(Order.created_at <= end)
        query = query.where(ProductionStage.order_id.in_(order_subq))

    if stage:
        query = query.where(ProductionStage.stage_name == stage)

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "order_id": r.order_id,
            "stage_name": r.stage_name.value,
            "status": r.status.value,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in records
    ]


def production_report_to_csv(data: list[dict]) -> str:
    headers = ["ID", "Order ID", "Stage", "Status", "Started At", "Completed At"]
    rows = [
        [r["id"], r["order_id"], r["stage_name"], r["status"],
         r["started_at"] or "", r["completed_at"] or ""]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Low Stock Materials Report ───────────────────────────

async def get_low_stock_report(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Material)
        .join(Inventory)
        .where(Inventory.quantity_on_hand <= Material.low_stock_threshold)
        .where(Material.low_stock_threshold > 0)
        .order_by(Material.name)
    )
    materials = result.scalars().all()

    rows = []
    for m in materials:
        qty = m.inventory.quantity_on_hand if m.inventory else Decimal("0")
        rows.append({
            "id": m.id,
            "name": m.name,
            "sku": m.sku,
            "unit": m.unit,
            "quantity_on_hand": float(qty),
            "low_stock_threshold": float(m.low_stock_threshold),
            "missing": float(m.low_stock_threshold - qty),
        })
    return rows


def low_stock_to_csv(data: list[dict]) -> str:
    headers = ["ID", "Material", "SKU", "Unit", "Available", "Minimum", "Missing"]
    rows = [
        [r["id"], r["name"], r["sku"], r["unit"],
         r["quantity_on_hand"], r["low_stock_threshold"], r["missing"]]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Customer Discount Report ─────────────────────────────

async def get_customer_discount_report(db: AsyncSession) -> list[dict]:
    from app.users.models import User, UserRole
    from app.customers.models import Customer

    users_result = await db.execute(
        select(User).where(User.role == UserRole.simple_user).order_by(User.email)
    )
    users = users_result.scalars().all()

    customer_ids = [u.customer_id for u in users if u.customer_id]

    customers_map: dict[int, Customer] = {}
    orders_by_customer: dict[int, list] = {}

    if customer_ids:
        cust_result = await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))
        customers_map = {c.id: c for c in cust_result.scalars().all()}

        orders_result = await db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.customer_id.in_(customer_ids))
            .where(Order.status.not_in([OrderStatus.cancelled, OrderStatus.draft]))
        )
        for o in orders_result.scalars().unique().all():
            orders_by_customer.setdefault(o.customer_id, []).append(o)

    rows = []
    for user in users:
        customer = customers_map.get(user.customer_id) if user.customer_id else None
        orders = orders_by_customer.get(user.customer_id, []) if user.customer_id else []
        total_revenue = sum(
            sum(Decimal(str(i.unit_price)) * i.quantity for i in o.items)
            for o in orders
        )
        rows.append({
            "user_id": user.id,
            "email": user.email,
            "customer_name": customer.name if customer else None,
            "company_name": customer.company_name if customer else None,
            "discount_percent": float(user.discount_percent),
            "total_orders": len(orders),
            "total_revenue": float(total_revenue),
        })
    return rows


def customer_discount_to_csv(data: list[dict]) -> str:
    headers = ["User ID", "Email", "Customer", "Company", "Discount %", "Total Orders", "Total Revenue"]
    rows = [
        [r["user_id"], r["email"], r["customer_name"] or "", r["company_name"] or "",
         r["discount_percent"], r["total_orders"], r["total_revenue"]]
        for r in data
    ]
    return _to_csv(headers, rows)


# ── Damaged Stock (Խոտան) Report ─────────────────────────
# Reads ONLY ProductVariant.damaged_stock_quantity. Does not touch sellable
# stock or production logic. Lists variants with damaged > 0; aggregates totals.

async def get_damaged_stock_report(db: AsyncSession) -> dict:
    from app.products.models import Product, ProductVariant

    result = await db.execute(
        select(ProductVariant, Product)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.damaged_stock_quantity > 0)
        .order_by(Product.name, ProductVariant.size, ProductVariant.color)
    )

    items: list[dict] = []
    affected_products: set[int] = set()
    total_damaged = 0
    for variant, product in result.all():
        items.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "variant_id": variant.id,
            "size": variant.size,
            "color": variant.color,
            "damaged_stock_quantity": variant.damaged_stock_quantity,
        })
        affected_products.add(product.id)
        total_damaged += variant.damaged_stock_quantity

    return {
        "summary": {
            "total_damaged": total_damaged,
            "products_affected": len(affected_products),
            "variants_affected": len(items),
        },
        "items": items,
    }


def damaged_stock_to_csv(data: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    s = data["summary"]
    writer.writerow(["Damaged Stock Report Summary"])
    writer.writerow(["Total Damaged", s["total_damaged"]])
    writer.writerow(["Products Affected", s["products_affected"]])
    writer.writerow(["Variants Affected", s["variants_affected"]])
    writer.writerow([])
    writer.writerow(["Product", "SKU", "Size", "Color", "Damaged Quantity"])
    for r in data["items"]:
        writer.writerow([r["product_name"], r["sku"], r["size"], r["color"], r["damaged_stock_quantity"]])
    return output.getvalue()
