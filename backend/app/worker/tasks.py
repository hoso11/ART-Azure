import io
import asyncio
from PIL import Image
from loguru import logger
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from app.config import settings


def get_sync_session():
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(name="app.worker.tasks.process_image")
def process_image(bucket: str, key: str):
    """Resize and optimize an uploaded product image. Backend-agnostic:
    routes through the StorageService abstraction so it works against MinIO
    (local dev) or Azure Blob (Azure deploy) without conditional code."""
    from app.storage.interface import get_storage_service

    logger.info("task.process_image.start", key=key)
    storage = get_storage_service()

    try:
        # Storage interface is async; Celery tasks are sync. asyncio.run
        # spins a fresh loop per call — fine for an occasional image task.
        image_data, _ = asyncio.run(storage.download_file(bucket, key))

        img = Image.open(io.BytesIO(image_data))

        # Resize if larger than 1200px
        max_size = (1200, 1200)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save optimized
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        optimized = output.getvalue()

        # Re-upload
        asyncio.run(storage.upload_file(bucket, key, optimized, "image/jpeg"))
        logger.info("task.process_image.done", key=key, original_size=len(image_data), new_size=len(optimized))
    except Exception as e:
        logger.error("task.process_image.failed", key=key, error=str(e))
        raise


@celery_app.task(name="app.worker.tasks.send_order_notification")
def send_order_notification(order_id: int, new_status: str, customer_email: str):
    """Send email notification when order status changes."""
    logger.info("task.send_order_notification", order_id=order_id, status=new_status)

    try:
        from app.email.smtp_adapter import SMTPEmailService
        service = SMTPEmailService()

        subject = f"Order #{order_id} — Status Update"
        body = (
            f"Your order #{order_id} has been updated.\n\n"
            f"New status: {new_status}\n\n"
            f"If you have questions, please contact our team.\n\n"
            f"— {settings.app_name}"
        )

        asyncio.run(service.send_email(customer_email, subject, body))
    except Exception as e:
        logger.error("task.send_order_notification.failed", order_id=order_id, error=str(e))


@celery_app.task(name="app.worker.tasks.send_low_stock_alert")
def send_low_stock_alert(material_name: str, current_qty: float, threshold: float, admin_email: str):
    """Send low stock alert email to admin."""
    logger.info("task.send_low_stock_alert", material=material_name, qty=current_qty)

    try:
        from app.email.smtp_adapter import SMTPEmailService
        service = SMTPEmailService()

        subject = f"Low Stock Alert: {material_name}"
        body = (
            f"Material '{material_name}' is below the minimum threshold.\n\n"
            f"Current quantity: {current_qty}\n"
            f"Threshold: {threshold}\n\n"
            f"Please reorder this material as soon as possible.\n\n"
            f"— {settings.app_name}"
        )

        asyncio.run(service.send_email(admin_email, subject, body))
    except Exception as e:
        logger.error("task.send_low_stock_alert.failed", material=material_name, error=str(e))


@celery_app.task(name="app.worker.tasks.generate_report")
def generate_report(report_type: str):
    """Generate a report on demand."""
    logger.info("task.generate_report.start", type=report_type)

    db = get_sync_session()
    try:
        if report_type == "orders":
            from app.orders.models import Order
            orders = db.query(Order).all()
            logger.info("task.generate_report.done", type=report_type, count=len(orders))
            return {"type": report_type, "count": len(orders)}
        else:
            logger.warning("task.generate_report.unknown_type", type=report_type)
            return {"type": report_type, "error": "unknown report type"}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.daily_stock_check")
def daily_stock_check():
    """Scheduled task: check all materials for low stock and send alerts."""
    logger.info("task.daily_stock_check.start")

    db = get_sync_session()
    try:
        from app.inventory.models import Material, Inventory
        from app.users.models import User

        materials = db.query(Material).join(Inventory).filter(
            Inventory.quantity_on_hand <= Material.low_stock_threshold,
            Material.low_stock_threshold > 0,
        ).all()

        if not materials:
            logger.info("task.daily_stock_check.all_ok")
            return

        # Get admin emails
        admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
        admin_emails = [a.email for a in admins]

        for material in materials:
            qty = float(material.inventory.quantity_on_hand) if material.inventory else 0
            threshold = float(material.low_stock_threshold)
            for email in admin_emails:
                send_low_stock_alert.delay(material.name, qty, threshold, email)

        logger.info("task.daily_stock_check.done", low_stock_count=len(materials))
    finally:
        db.close()
