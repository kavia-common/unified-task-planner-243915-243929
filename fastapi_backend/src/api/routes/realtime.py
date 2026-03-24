from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from src.core.security import decode_token
from src.realtime.manager import manager

router = APIRouter(tags=["Realtime"])


@router.get(
    "/realtime/help",
    summary="WebSocket usage help",
    description=(
        "Connect to WebSocket at `/ws` using a JWT access token.\n\n"
        "Example (browser):\n"
        "  const ws = new WebSocket(`ws://HOST/ws?token=ACCESS_TOKEN`)\n\n"
        "Events are JSON messages of shape: `{type: string, data: object}`.\n"
    ),
)
async def realtime_help() -> dict:
    return {
        "websocket_url": "/ws?token=ACCESS_TOKEN",
        "message_format": {"type": "task.created|task.updated|...", "data": {}},
    }


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for realtime events.

    Query params:
    - token: JWT access token from /auth/login

    Messages:
    - Server -> Client: JSON text of shape `{type: string, data: object}`
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = UUID(payload.get("sub"))
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            # We don't require client messages, but we keep the socket alive.
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception:
        await manager.disconnect(user_id, websocket)
