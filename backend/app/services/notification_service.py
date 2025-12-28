"""Notification service for real-time event broadcasting."""
import json
import logging
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

import redis
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for publishing real-time events via Redis pub/sub."""

    CHANNEL = "cartulary:events"

    def __init__(self):
        self.redis = None
        self.sync_redis = None

    async def get_redis(self):
        """Get or create async Redis connection."""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self.redis

    def get_sync_redis(self):
        """Get or create sync Redis connection."""
        if self.sync_redis is None:
            self.sync_redis = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self.sync_redis

    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish event to Redis pub/sub channel (async)."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client = await self.get_redis()
        await redis_client.publish(self.CHANNEL, json.dumps(event))
        logger.debug(f"Published event: {event_type}")

    def publish_event_sync(self, event_type: str, data: Dict[str, Any]):
        """Publish event to Redis pub/sub channel (sync)."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client = self.get_sync_redis()
        result = redis_client.publish(self.CHANNEL, json.dumps(event))
        logger.info(f"Published event (sync) to {result} subscribers: {event_type} - {data}")

    async def notify_document_created(self, document_id: UUID, user_id: UUID):
        """Notify that a document was created (async)."""
        await self.publish_event(
            "document.created",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )

    def notify_document_created_sync(self, document_id: UUID, user_id: UUID):
        """Notify that a document was created (sync)."""
        self.publish_event_sync(
            "document.created",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )

    async def notify_status_changed(
        self, document_id: UUID, old_status: str, new_status: str
    ):
        """Notify that document status changed (async)."""
        await self.publish_event(
            "document.status_changed",
            {
                "document_id": str(document_id),
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    def notify_status_changed_sync(
        self, document_id: UUID, old_status: str, new_status: str
    ):
        """Notify that document status changed (sync)."""
        self.publish_event_sync(
            "document.status_changed",
            {
                "document_id": str(document_id),
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    async def notify_document_updated(self, document_id: UUID, user_id: UUID):
        """Notify that document was updated (async)."""
        await self.publish_event(
            "document.updated",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )

    def notify_document_updated_sync(self, document_id: UUID, user_id: UUID):
        """Notify that document was updated (sync)."""
        self.publish_event_sync(
            "document.updated",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )

    async def notify_document_deleted(self, document_id: UUID, user_id: UUID):
        """Notify that document was deleted (async)."""
        await self.publish_event(
            "document.deleted",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )

    def notify_document_deleted_sync(self, document_id: UUID, user_id: UUID):
        """Notify that document was deleted (sync)."""
        self.publish_event_sync(
            "document.deleted",
            {"document_id": str(document_id), "user_id": str(user_id)},
        )


notification_service = NotificationService()
