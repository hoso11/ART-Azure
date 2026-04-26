from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "daily-stock-check": {
        "task": "app.worker.tasks.daily_stock_check",
        "schedule": crontab(hour=6, minute=0),  # Every day at 06:00 UTC
    },
}
