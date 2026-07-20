from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
from uuid import UUID
import json
import asyncio
from app.core.security import verify_token

router = APIRouter(prefix="/ws", tags=["WebSockets"])


class ConnectionManager:
    def __init__(self):
        # company_id -> set of websockets
        self.company_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> websocket
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, company_id: str, user_id: str):
        await websocket.accept()
        if company_id not in self.company_connections:
            self.company_connections[company_id] = set()
        self.company_connections[company_id].add(websocket)
        self.user_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, company_id: str, user_id: str):
        if company_id in self.company_connections:
            self.company_connections[company_id].discard(websocket)
        self.user_connections.pop(user_id, None)

    async def broadcast_to_company(self, company_id: str, message: dict):
        """Broadcast a message to all users in a company."""
        dead = set()
        for ws in self.company_connections.get(company_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.company_connections[company_id].discard(ws)

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to a specific user."""
        ws = self.user_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.user_connections.pop(user_id, None)

    async def broadcast_dispatch_update(self, company_id: str, dispatch_data: dict):
        await self.broadcast_to_company(company_id, {
            "type": "dispatch_update",
            "data": dispatch_data,
        })

    async def broadcast_order_update(self, company_id: str, order_data: dict):
        await self.broadcast_to_company(company_id, {
            "type": "order_update",
            "data": order_data,
        })

    async def broadcast_driver_location(self, company_id: str, location_data: dict):
        await self.broadcast_to_company(company_id, {
            "type": "driver_location",
            "data": location_data,
        })

    async def broadcast_notification(self, company_id: str, notification: dict):
        await self.broadcast_to_company(company_id, {
            "type": "notification",
            "data": notification,
        })


manager = ConnectionManager()


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket connection endpoint. Pass token as query param."""
    subject = verify_token(token)
    if not subject:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # For simplicity, use user_id as company_id context key
    # In production, look up company_id from DB
    user_id = subject
    company_id = "default"  # Should be fetched from DB based on user

    await manager.connect(websocket, company_id, user_id)

    try:
        # Send connected confirmation
        await websocket.send_json({
            "type": "connected",
            "data": {"user_id": user_id, "message": "Connected to Western Haul Dispatch"}
        })

        # Keep connection alive and handle messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                message = json.loads(data)

                # Handle client messages
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                elif message.get("type") == "driver_location":
                    # Broadcast driver location to company
                    await manager.broadcast_driver_location(
                        company_id, message.get("data", {})
                    )

            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, company_id, user_id)
    except Exception:
        manager.disconnect(websocket, company_id, user_id)
