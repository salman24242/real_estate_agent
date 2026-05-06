"""Celery app + beat schedule for background jobs."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.config import settings

celery_app = Celery(
    "real_estate_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.workers.tasks"],
)

celery_app.conf.beat_schedule = {
    "check-saved-searches-every-6-hours": {
        "task": "check_saved_searches",
        "schedule": crontab(minute=0, hour="*/6"),
    }
}
celery_app.conf.timezone = "UTC"
