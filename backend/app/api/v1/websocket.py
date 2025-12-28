"""WebSocket endpoint for real-time updates."""
import asyncio
import logging
from typing import Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
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
