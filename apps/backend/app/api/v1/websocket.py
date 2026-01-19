"""WebSocket endpoint for real-time updates."""
import asyncio
import logging
from typing import Set

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

REDIS_CHANNEL = "cartulary:events"


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._redis_task: asyncio.Task = None
        self._redis_client = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

        # Start Redis subscriber if this is the first connection
        if self._redis_task is None or self._redis_task.done():
            self._redis_task = asyncio.create_task(self._redis_subscriber())

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return
        logger.info(f"Broadcasting to {len(self.active_connections)} connections: {message[:100]}...")
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
                logger.debug("Message sent successfully to client")
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.add(connection)

        # Clean up dead connections
        if dead_connections:
            logger.info(f"Removing {len(dead_connections)} dead connections")
            self.active_connections -= dead_connections

    async def _redis_subscriber(self):
        """Subscribe to Redis pub/sub and broadcast messages to WebSocket clients."""
        logger.info("Starting Redis pub/sub subscriber...")
        try:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            pubsub = self._redis_client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            logger.info(f"Subscribed to Redis channel: {REDIS_CHANNEL}")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    logger.info(f"Received Redis message: {message['data'][:100]}...")
                    await self.broadcast(message["data"])
        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
        finally:
            if self._redis_client:
                await self._redis_client.close()
                self._redis_client = None


manager = ConnectionManager()


async def verify_token(token: str) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for real-time updates."""
    # Verify authentication
    payload = await verify_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    user_id = payload.get("sub")
    logger.info(f"WebSocket connected: user={user_id}")

    await manager.connect(websocket)

    try:
        # Keep connection alive with heartbeat
        while True:
            try:
                # Wait for pong or timeout
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
