"""Background service to broadcast Redis events to WebSocket clients."""
import logging

import redis.asyncio as aioredis
from app.api.v1.websocket import manager
from app.config import settings

logger = logging.getLogger(__name__)


async def start_broadcaster():
    """Subscribe to Redis pub/sub and broadcast to WebSocket clients."""
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe("cartulary:events")

    logger.info("WebSocket broadcaster started, listening on channel: cartulary:events")

    try:
        async for message in pubsub.listen():
            logger.debug(f"Received Redis message: {message}")
            if message["type"] == "message":
                logger.info(f"Broadcasting message to {len(manager.active_connections)} WebSocket clients: {message['data'][:100]}...")
                # Broadcast to all WebSocket connections
                await manager.broadcast(message["data"])
            elif message["type"] == "subscribe":
                logger.info(f"Successfully subscribed to channel: {message['channel']}")
    except Exception as e:
        logger.error(f"Broadcaster error: {e}", exc_info=True)
    finally:
        await pubsub.unsubscribe("cartulary:events")
        await redis.close()
        logger.info("WebSocket broadcaster stopped")
