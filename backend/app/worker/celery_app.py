from celery import Celery
from app.config import settings
from app.worker.beat_schedule import CELERY_BEAT_SCHEDULE

celery_app = Celery(
    "art_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
    task_routes={
        "app.worker.tasks.process_image": {"queue": "images"},
        "app.worker.tasks.send_order_notification": {"queue": "notifications"},
        "app.worker.tasks.send_low_stock_alert": {"queue": "notifications"},
        "app.worker.tasks.generate_report": {"queue": "reports"},
        "app.worker.tasks.daily_stock_check": {"queue": "default"},
    },
)

celery_app.autodiscover_tasks(["app.worker"])
