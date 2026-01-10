"""Celery tasks module."""
from app.tasks.celery_app import celery_app
from app.tasks.document_tasks import process_document, reprocess_document

__all__ = ["celery_app", "process_document", "reprocess_document"]
