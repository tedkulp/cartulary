"""Celery application configuration."""
import logging
from celery import Celery
from celery.signals import worker_ready

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "cartulary",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_tasks"],  # Include task modules
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Run startup checks when Celery worker is ready."""
    logger.info("Celery worker ready, running startup checks...")
    try:
        from app.core.startup import startup_checks
        startup_checks()
    except Exception as e:
        logger.error(f"Celery worker startup validation failed: {e}")
        # Log but don't crash the worker
