# # -------------------
# # 📁 router/chat_router.py
# # -------------------
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from app.services.chat import ChatService, WebSocketManager
# from datetime import datetime
# from app.services.user import UserService
# from app.core.keycloak import decode_token
# from app.services.request import RequestService
# from app.services.project import ProjectService
# from app.services.agreements import AgreementService
# from app.services.user import UserService
# from starlette import status

# router = APIRouter()

# chat_service = ChatService()
# websocket_manager = WebSocketManager()
# request_service = RequestService()
# project_service = ProjectService()
# agreement_service = AgreementService()
# user_service = UserService()



# @router.websocket("/ws/project/{project_id}/{user_id}")
# async def ws(project_id: str, user_id: str, websocket: WebSocket):
#     # If you use a token, validate BEFORE or right after accept(), and close explicitly.
#     await websocket.accept()
#     try:
#         user = UserService().get_user(user_id)  # must NOT raise HTTPException
#         # print("User fetched for WS:", user_id, user)
#         if not user:
#             await websocket.close(code=status.WS_1008_POLICY_VIOLATION); return
        
#         project_details = project_service.get(project_id)
#         if not project_details:
#             await websocket.send_json({"error": "Project not found"})
#         user_details = user_service.get_user(user_id)
#         if not user_details:
#             await websocket.send_json({"error": "User not found"})

#         # Send history safely (avoid raw ObjectId)
#         for chat in chat_service.get_chat_history(project_id, "project"):
#             chat.pop("_id", None)
#             await websocket.send_json(chat)

#         # Main loop
#         while True:
#             msg = await websocket.receive_json()  # may raise if bad JSON
#             content = (msg.get("content") or "").strip()
#             if not content:
#                 await websocket.send_json({"error": "Message cannot be empty"}); continue

#             chat_service.log_chat("project", project_id, user_id, content, user["role"], user.get("first_name", ""), user.get("last_name", ""))
#             await websocket_manager.send_to_group(project_id, {
#                 "user_id": user_id,
#                 "message": content,
#                 "role": user["role"],
#                 "user_name": user.get("first_name", "") + " " + user.get("last_name", ""),
#                 "timestamp": datetime.utcnow().isoformat()
#             })
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         # log the error; don’t let it bubble and kill the socket silently
#         print("WS error:", repr(e))
#         try:
#             await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
#         except Exception:
#             pass
#     finally:
#         await websocket_manager.disconnect(user_id, project_id)


# @router.websocket("/ws/agreement/{agreement_id}/{user_id}")
# async def ws(agreement_id: str, user_id: str, websocket: WebSocket):
#     # If you use a token, validate BEFORE or right after accept(), and close explicitly.
#     await websocket.accept()
#     try:
#         user = UserService().get_user(user_id)  # must NOT raise HTTPException
#         # print("User fetched for WS:", user_id, user)
#         if not user:
#             await websocket.close(code=status.WS_1008_POLICY_VIOLATION); return
        
#         agreement_details = agreement_service.get_agreement(agreement_id)
#         if not agreement_details:
#             await websocket.send_json({"error": "Agreement not found"})
        
#         user_details = user_service.get_user(user_id)
#         if not user_details:
#             await websocket.send_json({"error": "User not found"})

#         # Send history safely (avoid raw ObjectId)
#         for chat in chat_service.get_chat_history(agreement_id, "agreement"):
#             chat.pop("_id", None)
#             await websocket.send_json(chat)

#         # Main loop
#         while True:
#             msg = await websocket.receive_json()  # may raise if bad JSON
#             content = (msg.get("content") or "").strip()
#             if not content:
#                 await websocket.send_json({"error": "Message cannot be empty"}); continue
            
            

#             chat_service.log_chat("agreement", agreement_id, user_id, content, user["role"], user.get("first_name", ""), user.get("last_name", ""))
#             await websocket_manager.send_to_group(agreement_id, {
#                 "user_id": user_id,
#                 "message": content,
#                 "role": user["role"],
#                 "user_name": user.get("first_name", "") + " " + user.get("last_name", ""),
#                 "timestamp": datetime.utcnow().isoformat()
#             })
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         # log the error; don’t let it bubble and kill the socket silently
#         print("WS error:", repr(e))
#         try:
#             await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
#         except Exception:
#             pass
#     finally:
#         await websocket_manager.disconnect(user_id, agreement_id)



# app/router/chat_router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from starlette import status
from typing import Optional
from app.services.chat import ChatService, WebSocketManager
from app.services.request import RequestService
from app.services.user import UserService
from app.core.keycloak import get_current_user, _validate_token_and_get_user
from app.services.project import ProjectService
from app.services.agreements import AgreementService
import traceback

router = APIRouter()

# singletons (or inject via Depends if you prefer)
websocket_manager = WebSocketManager()

# Helper: determine if user can join arbitrary group
def _is_privileged(user: dict) -> bool:
    # adjust according to your user model or token claims
    role = user.get("role")
    privileged_roles = {"admin", "SA", "customer_care", "support"}
    # if Keycloak uses realm_access.roles:
    if role in privileged_roles:
        return True
    return False

# A helper to fetch current user from token
# def _user_from_token_or_none(token: str):
#     if not token:
#         return None
#     try:
#         claims = decode_token(token)  # your existing function
#         # you may need to shape claims -> standard user dict used in rest of app
#         # example: claims['sub'] is user id, claims['given_name'], claims['family_name']
#         user = {
#             "id": claims.get("sub"),
#             "user_id": claims.get("sub"),
#             "first_name": claims.get("given_name") or claims.get("first_name"),
#             "last_name": claims.get("family_name") or claims.get("last_name"),
#             "email": claims.get("email"),
#             "role": claims.get("role") or claims.get("preferred_role")  # adapt per your token
#         }
#         # also keep raw claims for role checks
#         user["realm_access"] = claims.get("realm_access")
#         return user
#     except Exception:
#         return None


@router.websocket("/ws/project/{request_id}")
async def ws_project(request_id: str, websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Connect to project group chat.
    Clients must pass ?token=<keycloak_token> in websocket URL.
    """
    print(f"🔌 WebSocket connection attempt: request_id={request_id}, token_present={bool(token)}")
    # Accept connection first (required by WebSocket protocol)
    await websocket.accept()
    try:
        # Validate token after accepting connection
        if not token:
            print("❌ WebSocket rejected: No token provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token is required")
            return
        
        try:
            caller = _validate_token_and_get_user(token)
            if not caller:
                print("❌ WebSocket rejected: Invalid token (caller is None)")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
                return
            print(f"✅ WebSocket authenticated: user_id={caller.get('user_id')}")
        except HTTPException as e:
            print(f"❌ WebSocket rejected: HTTPException - {e.detail}")
            await websocket.send_json({"error": e.detail})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e.detail))
            return
        except Exception as e:
            print(f"❌ WebSocket rejected: Exception during auth - {str(e)}")
            traceback.print_exc()
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return

        # allow privileged roles to join any project; otherwise ensure membership (simple example)
        request_service = RequestService()
        project_service = ProjectService()
        request_details = request_service.request_get_one(request_id)
        print("Request details for chat:", request_details)
        if not request_details:
            await websocket.send_json({"error": "Request not found"})
            await websocket.close()
            return
        project_id = request_details.get("project_id")
        print("Project ID for request:", project_id)
        if not project_id:
            await websocket.send_json({"error": "Request has no associated project"})
            await websocket.close()
            return
        project_details = project_service.get(project_id)
        if not project_details:
            await websocket.send_json({"error": "Project not found"})
            await websocket.close()
            return

        # If caller is not privileged, make sure they are part of the project participants
        if not _is_privileged(caller):
            # your project model might have 'client_id' and 'freelancer_id' etc.
            participants = list()
            if request_details:
                participants.append(request_details.get("client_id"))
                participants.append(request_details.get("freelancer_id"))
            print("Project participants:", participants)
            print("Caller user ID:", caller.get("user_id"))
            print(request_details.get("client_id"), request_details.get("freelancer_id"))

            if caller.get("user_id") not in participants:
                await websocket.send_json({"error": "Not authorized to join this project chat"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        # register connection with in-memory manager
        await websocket_manager.connect(websocket, caller["user_id"], f"project::{project_id}")

        # create chat service instance (pass your DB)
        chat_service = ChatService()

        # Send last N messages
        history = chat_service.get_chat_history("project", project_id, limit=100)
        for h in history:
            await websocket.send_json({"type": "history", "payload": h})

        # Main loop
        while True:
            data = await websocket.receive_json()
            content = (data.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"}); continue

            saved = chat_service.log_chat("project", request_id=request_id, group_id=project_id, sender_user=caller, content=content)
            # broadcast to group (other participants)
            payload = {
                "type": "message",
                "payload": {
                    "group_type": "project",
                    "request_id": request_id,
                    "group_id": project_id,
                    "message": saved,
                }
            }
            await websocket_manager.send_to_group(f"project::{project_id}", payload)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        traceback.print_exc()
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        await websocket_manager.disconnect(websocket)


@router.websocket("/ws/agreement/{agreement_id}")
async def ws_agreement(agreement_id: str, websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Connect to agreement group chat.
    Clients must pass ?token=<keycloak_token> in websocket URL.
    """
    print(f"🔌 Agreement WebSocket connection attempt: agreement_id={agreement_id}, token_present={bool(token)}")
    # Accept connection first (required by WebSocket protocol)
    await websocket.accept()
    try:
        # Validate token after accepting connection
        if not token:
            print("❌ Agreement WebSocket rejected: No token provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token is required")
            return
        
        try:
            caller = _validate_token_and_get_user(token)
            if not caller:
                print("❌ Agreement WebSocket rejected: Invalid token (caller is None)")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
                return
            print(f"✅ Agreement WebSocket authenticated: user_id={caller.get('user_id')}")
        except HTTPException as e:
            print(f"❌ Agreement WebSocket rejected: HTTPException - {e.detail}")
            await websocket.send_json({"error": e.detail})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e.detail))
            return
        except Exception as e:
            print(f"❌ Agreement WebSocket rejected: Exception during auth - {str(e)}")
            traceback.print_exc()
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return

        # load agreement
        agreement_service = AgreementService()
        agreement_details = agreement_service.get_agreement(agreement_id)
        if not agreement_details:
            await websocket.send_json({"error": "Agreement not found"})
            await websocket.close()
            return
        
        # Check if agreement is paused - block sending messages but allow viewing
        agreement_status = agreement_details.get("status", "")
        is_paused = agreement_status == "Paused"

        # build participant set and normalize IDs
        participants = set()
        print("Agreement details:", agreement_details)
        print("Client ID:", agreement_details.get("client", {}).get("user_id"))
        print("Freelancer ID:", agreement_details.get("freelancer", {}).get("user_id"))

        client_id = agreement_details.get("client", {}).get("user_id")
        freelancer_id = agreement_details.get("freelancer", {}).get("user_id")

        if client_id:
            participants.add(str(client_id))
        if freelancer_id:
            participants.add(str(freelancer_id))

        print("Agreement participants:", participants)
        caller_user_id = str(caller.get("user_id"))

        if not participants or str(caller_user_id) not in participants:
            if not _is_privileged(caller):
                await websocket.send_json({"error": "Agreement has no participants"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        
        # register connection (use same user id key as other websockets)
        await websocket_manager.connect(websocket, str(caller_user_id), f"agreement::{agreement_id}")

        chat_service = ChatService()

        # Send last N messages
        history = chat_service.get_chat_history("agreement", agreement_id, limit=100) or []
        for h in history:
            await websocket.send_json({"type": "history", "payload": h})

        # Main receive/send loop
        while True:
            data = await websocket.receive_json()
            content = (data.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"})
                continue

            # Check if agreement is paused - refresh status on each message attempt
            current_agreement = agreement_service.get_agreement(agreement_id)
            if current_agreement and current_agreement.get("status") == "Paused":
                await websocket.send_json({
                    "error": "This agreement is currently paused. You cannot send messages until it is unpaused by the administrator."
                })
                continue

            # log chat: request_id is None here
            saved = chat_service.log_chat(
                "agreement",
                request_id=None,
                group_id=agreement_id,
                sender_user=caller,
                content=content
            )

            payload = {
                "type": "message",
                "payload": {
                    "group_type": "agreement",
                    "group_id": agreement_id,
                    "message": saved,
                }
            }
            # broadcast to group
            await websocket_manager.send_to_group(f"agreement::{agreement_id}", payload)

    except WebSocketDisconnect:
        # normal disconnect
        pass
    except Exception:
        traceback.print_exc()
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        # ensure cleanup
        try:
            await websocket_manager.disconnect(websocket)
        except Exception:
            pass
