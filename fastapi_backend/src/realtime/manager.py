import asyncio
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    """Manages per-user WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            if user_id in self._connections and websocket in self._connections[user_id]:
                self._connections[user_id].remove(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]

    async def send(self, user_id: UUID, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                # Ignore transient failures; client will reconnect.
                pass

    async def broadcast_to_user(self, user_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        await self.send(user_id, {"type": event_type, "data": data})


manager = ConnectionManager()
