"""
api/websocket.py
WebSocket endpoint that streams live signal state to the React dashboard.
The frontend connects once and receives updates every second automatically.
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db.redis_client import get_signal_state

router   = APIRouter()
logger   = logging.getLogger(__name__)
PUSH_HZ  = 1.0   # push state to clients every 1 second


class ConnectionManager:
    """Tracks all active WebSocket connections per junction."""

    def __init__(self):
        # {junction_id: [WebSocket, ...]}
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, junction_id: int, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(junction_id, []).append(ws)
        logger.info(f"WS connected — junction={junction_id} total={len(self._connections[junction_id])}")

    def disconnect(self, junction_id: int, ws: WebSocket):
        conns = self._connections.get(junction_id, [])
        if ws in conns:
            conns.remove(ws)
        logger.info(f"WS disconnected — junction={junction_id}")

    async def broadcast(self, junction_id: int, data: dict):
        """Send signal state to all clients watching this junction."""
        dead = []
        for ws in self._connections.get(junction_id, []):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(junction_id, ws)


manager = ConnectionManager()


@router.websocket("/junction/{junction_id}")
async def junction_stream(websocket: WebSocket, junction_id: int):
    """
    React dashboard connects here:
      ws://localhost:8000/ws/junction/1

    Every second, the latest signal state is pushed to the client.
    No messages are expected from the client (read-only stream).
    """
    await manager.connect(junction_id, websocket)
    try:
        while True:
            state = await get_signal_state(junction_id)
            if state:
                await manager.broadcast(junction_id, state)
            else:
                await websocket.send_text(json.dumps({
                    "junction_id": junction_id,
                    "error": "No state available — controller may be starting up"
                }))
            await asyncio.sleep(PUSH_HZ)
    except WebSocketDisconnect:
        manager.disconnect(junction_id, websocket)
