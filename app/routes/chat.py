# -------------------
# 📁 router/chat_router.py
# -------------------
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.chat import ChatService, WebSocketManager
from datetime import datetime
from app.services.user import UserService
from app.core.keycloak import decode_token
from app.services.request import RequestService
from starlette import status

router = APIRouter()

chat_service = ChatService()
websocket_manager = WebSocketManager()


# @router.websocket("/ws/{project_id}/{user_id}")
# async def websocket_endpoint(project_id: str, user_id: str, websocket: WebSocket):

#     # ✅ Accept connection
#     await websocket.accept() 
#     await websocket_manager.connect(user_id, project_id, websocket)

#     user_detail = UserService().get_user(user_id)
#     if not user_detail:
#         await websocket.close(code=4404)  # 4404: User not found
#         return
    
#     # ✅ Validate project access
#     request_service = RequestService().project_exists(project_id, user_id, user_detail["role"])
#     if not request_service:
#         print("Project not found")
#         await websocket.close(code=4403)  # 4403: Forbidden
#         return

#     # ✅ Send chat history
#     chat_history = chat_service.get_chat_history(project_id)
#     for chat in chat_history:
#         chat.pop("_id", None)  # Avoid ObjectId serialization error
#         await websocket.send_json(chat)

#     try:
#         while True:
#             message = await websocket.receive_json()
#             content = message.get("content", "").strip()
#             if not content:
#                 await websocket.send_json({"error": "Message cannot be empty."})
#                 continue

#             chat_service.log_chat(
#                 project_id=project_id,
#                 user_id=user_id,
#                 message=content,
#                 role=user_detail["role"],
#                 user_name=user_detail["name"]
#             )

#             await websocket_manager.send_to_group(project_id, {
#                 "user_id": user_id,
#                 "message": content,
#                 "role": user_detail["role"],
#                 "user_name": user_detail["name"],
#                 "timestamp": datetime.utcnow().isoformat()
#             })
#     except WebSocketDisconnect:
#         await websocket_manager.disconnect(user_id, project_id)


@router.websocket("/ws/{project_id}/{user_id}")
async def ws(project_id: str, user_id: str, websocket: WebSocket):
    # If you use a token, validate BEFORE or right after accept(), and close explicitly.
    await websocket.accept()
    try:
        user = UserService().get_user(user_id)  # must NOT raise HTTPException
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION); return

        # Send history safely (avoid raw ObjectId)
        for chat in chat_service.get_chat_history(project_id):
            chat.pop("_id", None)
            await websocket.send_json(chat)

        # Main loop
        while True:
            msg = await websocket.receive_json()  # may raise if bad JSON
            content = (msg.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"}); continue

            chat_service.log_chat(project_id, user_id, content, user["role"], user.get("name", ""))
            await websocket_manager.send_to_group(project_id, {
                "user_id": user_id,
                "message": content,
                "role": user["role"],
                "user_name": user.get("name", ""),
                "timestamp": datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # log the error; don’t let it bubble and kill the socket silently
        print("WS error:", repr(e))
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        await websocket_manager.disconnect(user_id, project_id)