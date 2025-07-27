from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from app.services.chat import ChatService
from app.models.chat import MessageIn, MessageOut
from typing import List
from uuid import uuid4
from app.core.keycloak import get_current_user
from .manager import ConnectionManager

router = APIRouter(prefix="/chat", tags=["Chat"])
manager = ConnectionManager()

@router.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str, user_id: str, role: str):
    await manager.connect(chat_id, websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message")
            sender_id = user_id
            sender_role = role

            await manager.chat_service.send_message(chat_id, sender_id, sender_role, message)
            saved_msg = {
                "chat_id": chat_id,
                "sender_id": sender_id,
                "sender_role": sender_role,
                "message": message,
                "seen_by": [sender_id],
            }
            await manager.broadcast(chat_id, saved_msg)
    except WebSocketDisconnect:
        await manager.disconnect(chat_id, websocket, user_id)

@router.get("/{chat_id}/messages", response_model=List[MessageOut])
async def get_paginated_messages(
    chat_id: str,
    skip: int = Query(0),
    limit: int = Query(20),
    current_user=Depends(get_current_user),
    service: ChatService = Depends()
):
    await service.mark_all_seen(chat_id, current_user.id)
    return await service.get_chat_messages(chat_id, skip=skip, limit=limit)

@router.get("/{chat_id}/unread-count")
async def get_unread_count(
    chat_id: str,
    current_user=Depends(get_current_user),
    service: ChatService = Depends()
):
    return {"unread_count": await service.get_unread_message_count(chat_id, current_user.id)}
