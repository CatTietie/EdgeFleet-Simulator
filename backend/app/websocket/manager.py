"""WebSocket connection manager with Redis pub/sub fan-out."""
import asyncio
import logging
from dataclasses import dataclass, field

import jwt
import orjson
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class Connection:
    websocket: WebSocket
    org_id: str
    user_id: str


class WebSocketManager:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._connections: dict[str, list[Connection]] = {}  # org_id -> connections
        self._telemetry_counter: dict[str, int] = {}  # device_id -> counter (for sampling)

    async def connect(self, websocket: WebSocket, org_id: str, user_id: str):
        await websocket.accept()
        conn = Connection(websocket=websocket, org_id=org_id, user_id=user_id)
        if org_id not in self._connections:
            self._connections[org_id] = []
        self._connections[org_id].append(conn)
        logger.info(f"WS connected: user={user_id} org={org_id} (total: {self._count_connections()})")

    def disconnect(self, websocket: WebSocket, org_id: str):
        if org_id in self._connections:
            self._connections[org_id] = [
                c for c in self._connections[org_id] if c.websocket != websocket
            ]
            if not self._connections[org_id]:
                del self._connections[org_id]

    async def broadcast_to_org(self, org_id: str, message: dict):
        connections = self._connections.get(org_id, [])
        dead = []
        data = orjson.dumps(message)
        for conn in connections:
            try:
                await conn.websocket.send_bytes(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self._connections[org_id].remove(conn)

    async def publish_telemetry(self, data_point: dict):
        """Publish telemetry to WebSocket clients (sampled: every 5th reading per device)."""
        device_id = data_point["device_id"]
        self._telemetry_counter[device_id] = self._telemetry_counter.get(device_id, 0) + 1
        if self._telemetry_counter[device_id] % 5 != 0:
            return

        org_id = data_point["org_id"]
        message = {"type": "telemetry_update", "data": data_point}

        # Publish to Redis for multi-instance support
        channel = f"ws:org:{org_id}"
        try:
            await self.redis.publish(channel, orjson.dumps(message))
        except Exception:
            pass

    async def publish_status(self, status_event: dict):
        org_id = status_event["org_id"]
        message = {"type": "device_status_change", "data": status_event}
        channel = f"ws:org:{org_id}"
        try:
            await self.redis.publish(channel, orjson.dumps(message))
        except Exception:
            pass

    async def start_subscriber(self):
        """Subscribe to all org channels and fan out to WebSocket clients."""
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("ws:org:*")
        logger.info("WebSocket Redis subscriber started")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                org_id = channel.split(":")[-1]
                data = orjson.loads(message["data"])
                await self.broadcast_to_org(org_id, data)
            except Exception as e:
                logger.error(f"WS subscriber error: {e}")

    def _count_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Validate JWT
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        org_id = payload["org_id"]
        user_id = payload["sub"]
    except (jwt.InvalidTokenError, KeyError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    manager: WebSocketManager = websocket.app.state.ws_manager
    await manager.connect(websocket, org_id, user_id)

    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, org_id)
        logger.info(f"WS disconnected: user={user_id} org={org_id}")
