# -------------------
# 📁 router/chat_router.py
# -------------------
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.chat import ChatService, WebSocketManager
from datetime import datetime
from app.services.user import UserService
from app.core.keycloak import decode_token
from app.services.request import RequestService
from app.services.project import ProjectService
from app.services.agreements import AgreementService
from app.services.user import UserService
from starlette import status

router = APIRouter()

chat_service = ChatService()
websocket_manager = WebSocketManager()
request_service = RequestService()
project_service = ProjectService()
agreement_service = AgreementService()
user_service = UserService()



@router.websocket("/ws/project/{project_id}/{user_id}")
async def ws(project_id: str, user_id: str, websocket: WebSocket):
    # If you use a token, validate BEFORE or right after accept(), and close explicitly.
    await websocket.accept()
    try:
        user = UserService().get_user(user_id)  # must NOT raise HTTPException
        # print("User fetched for WS:", user_id, user)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION); return
        
        project_details = project_service.get(project_id)
        if not project_details:
            await websocket.send_json({"error": "Project not found"})
        user_details = user_service.get_user(user_id)
        if not user_details:
            await websocket.send_json({"error": "User not found"})

        # Send history safely (avoid raw ObjectId)
        for chat in chat_service.get_chat_history(project_id, "project"):
            chat.pop("_id", None)
            await websocket.send_json(chat)

        # Main loop
        while True:
            msg = await websocket.receive_json()  # may raise if bad JSON
            content = (msg.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"}); continue

            chat_service.log_chat("project", project_id, user_id, content, user["role"], user.get("first_name", ""), user.get("last_name", ""))
            await websocket_manager.send_to_group(project_id, {
                "user_id": user_id,
                "message": content,
                "role": user["role"],
                "user_name": user.get("first_name", "") + " " + user.get("last_name", ""),
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


@router.websocket("/ws/agreement/{agreement_id}/{user_id}")
async def ws(agreement_id: str, user_id: str, websocket: WebSocket):
    # If you use a token, validate BEFORE or right after accept(), and close explicitly.
    await websocket.accept()
    try:
        user = UserService().get_user(user_id)  # must NOT raise HTTPException
        # print("User fetched for WS:", user_id, user)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION); return
        
        agreement_details = agreement_service.get_agreement(agreement_id)
        if not agreement_details:
            await websocket.send_json({"error": "Agreement not found"})
        
        user_details = user_service.get_user(user_id)
        if not user_details:
            await websocket.send_json({"error": "User not found"})

        # Send history safely (avoid raw ObjectId)
        for chat in chat_service.get_chat_history(agreement_id, "agreement"):
            chat.pop("_id", None)
            await websocket.send_json(chat)

        # Main loop
        while True:
            msg = await websocket.receive_json()  # may raise if bad JSON
            content = (msg.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"}); continue
            
            

            chat_service.log_chat("agreement", agreement_id, user_id, content, user["role"], user.get("first_name", ""), user.get("last_name", ""))
            await websocket_manager.send_to_group(agreement_id, {
                "user_id": user_id,
                "message": content,
                "role": user["role"],
                "user_name": user.get("first_name", "") + " " + user.get("last_name", ""),
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
        await websocket_manager.disconnect(user_id, agreement_id)