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
from app.services.ticket import TicketService
import traceback
import asyncio

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


@router.websocket("/ws/private/{other_user_id}")
async def ws_private(
    other_user_id: str,
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    ticket_id: Optional[str] = Query(None)
):
    """
    Connect to private chat between admin and another user (client or freelancer).
    Clients must pass ?token=<keycloak_token> in websocket URL.
    Optional: ?ticket_id=<ticket_id> to link conversation to a dispute.
    """
    print(f"🔌 Private WebSocket connection attempt: other_user_id={other_user_id}, token_present={bool(token)}, ticket_id={ticket_id}")
    # Accept connection first (required by WebSocket protocol)
    await websocket.accept()
    try:
        # Validate token after accepting connection
        if not token:
            print("❌ Private WebSocket rejected: No token provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token is required")
            return
        
        try:
            caller = _validate_token_and_get_user(token)
            if not caller:
                print("❌ Private WebSocket rejected: Invalid token (caller is None)")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
                return
            caller_user_id = caller.get('user_id')
            caller_role = caller.get('role')
            print(f"✅ Private WebSocket authenticated: user_id={caller_user_id}, role={caller_role}")
            print(f"🔐 Token validation result: caller={caller}")
        except HTTPException as e:
            print(f"❌ Private WebSocket rejected: HTTPException - {e.detail}")
            await websocket.send_json({"error": e.detail})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e.detail))
            return
        except Exception as e:
            print(f"❌ Private WebSocket rejected: Exception during auth - {str(e)}")
            traceback.print_exc()
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return

        caller_id = str(caller.get("user_id"))
        caller_role = caller.get("role")
        other_user_id_str = str(other_user_id)
        
        print(f"🔍 Connection attempt details:")
        print(f"   - Caller ID: {caller_id}")
        print(f"   - Caller Role: {caller_role}")
        print(f"   - Other User ID (from URL): {other_user_id_str}")
        print(f"   - Ticket ID (from URL): {ticket_id}")

        # Authorization: Only admin can chat with CL/FL, and CL/FL can only chat with admin
        # Verify the other user exists and has correct role
        user_service = UserService()
        other_user = user_service.get_user(other_user_id_str)
        if not other_user:
            error_msg = f"User not found: {other_user_id_str}. Please verify the admin user ID is correct."
            print(f"❌ Private WebSocket rejected: {error_msg}")
            print(f"   Caller: user_id={caller_id}, role={caller_role}")
            await websocket.send_json({"type": "error", "error": error_msg})
            await asyncio.sleep(0.1)  # Give time for message to be sent
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        other_user_role = other_user.get("role")
        print(f"🔍 User lookup: other_user_id={other_user_id_str}, other_user_role={other_user_role}")

        # Check authorization rules - use same privileged roles as _is_privileged
        privileged_roles = {"admin", "SA", "customer_care", "support"}
        is_admin = caller_role in privileged_roles
        is_other_admin = other_user_role in privileged_roles
        print(f"🔐 Authorization check: caller_role={caller_role} (is_admin={is_admin}), other_role={other_user_role} (is_other_admin={is_other_admin})")

        if is_admin:
            # Admin can chat with CL or FL
            if other_user_role not in ["CL", "FL"]:
                error_msg = f"Admin can only chat with clients or freelancers, but other user has role: {other_user_role}"
                print(f"❌ Private WebSocket rejected: {error_msg}")
                await websocket.send_json({"type": "error", "error": error_msg})
                await asyncio.sleep(0.1)  # Give time for message to be sent
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        elif caller_role in ["CL", "FL"]:
            # CL/FL can only chat with admin
            if not is_other_admin:
                error_msg = f"You can only chat with admin privately. The user you're trying to chat with has role: {other_user_role} (expected one of: {privileged_roles})"
                print(f"❌ Private WebSocket rejected: {caller_role} can only chat with admin, got {other_user_role}")
                await websocket.send_json({"type": "error", "error": error_msg})
                await asyncio.sleep(0.1)  # Give time for message to be sent
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        else:
            # Other roles not allowed
            error_msg = f"Private chat not available for your role: {caller_role}"
            print(f"❌ Private WebSocket rejected: {error_msg}")
            await websocket.send_json({"type": "error", "error": error_msg})
            await asyncio.sleep(0.1)  # Give time for message to be sent
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Get project_id and agreement_id from ticket if provided
        # CRITICAL: Always normalize ticket_id to full ticket_id from database to ensure consistent group_id
        # This ensures both admin and client use the same group_id regardless of ticket_id format
        project_id = None
        agreement_id = None
        resolved_ticket_id = ticket_id  # Start with provided ticket_id
        if ticket_id:
            try:
                ticket_service = TicketService()
                ticket_data = None
                
                # First, try to get ticket by full ID
                try:
                    ticket_data = ticket_service.repo.get_ticket(ticket_id)
                except:
                    pass
                
                # If not found, try searching in user's tickets (handles partial IDs like last 8 chars)
                if not ticket_data:
                    try:
                        all_tickets = ticket_service.list_tickets(caller)
                        for ticket in all_tickets:
                            ticket_full_id = ticket.get("ticket_id", "")
                            # Match exact or if provided ticket_id is last 8 chars (case-insensitive)
                            ticket_id_upper = ticket_id.upper()
                            ticket_full_upper = ticket_full_id.upper()
                            if ticket_full_id == ticket_id or ticket_full_upper.endswith(ticket_id_upper):
                                ticket_data = ticket
                                break
                    except Exception as e:
                        print(f"⚠️ Could not list tickets for user: {e}")
                
                # CRITICAL: For admin users, also search ALL tickets if not found in user's list
                # This ensures admin can find tickets even if not directly assigned
                if not ticket_data and _is_privileged(caller):
                    try:
                        all_tickets = ticket_service.repo.get_all_tickets()
                        ticket_id_upper = ticket_id.upper()
                        for ticket in all_tickets:
                            ticket_full_id = ticket.get("ticket_id", "")
                            ticket_full_upper = ticket_full_id.upper()
                            # Match exact or if provided ticket_id is last 8 chars (case-insensitive)
                            if ticket_full_id == ticket_id or ticket_full_upper.endswith(ticket_id_upper):
                                ticket_data = ticket
                                print(f"📋 Found ticket in all tickets (admin access): {ticket_full_id}")
                                break
                    except Exception as e:
                        print(f"⚠️ Could not search all tickets: {e}")
                
                # CRITICAL: Always use full ticket_id from database if found
                # This ensures consistent group_id regardless of input format
                if ticket_data:
                    resolved_ticket_id = ticket_data.get("ticket_id")
                    if not resolved_ticket_id:
                        resolved_ticket_id = ticket_id  # Fallback to provided
                    project_id = ticket_data.get("project_id")
                    agreement_id = ticket_data.get("agreement_id")
                    print(f"📋 Normalized ticket_id: {ticket_id} -> {resolved_ticket_id} (project_id={project_id}, agreement_id={agreement_id})")
                else:
                    print(f"⚠️ Ticket not found. Using provided ticket_id as-is: {ticket_id}")
                    resolved_ticket_id = ticket_id
            except Exception as e:
                print(f"⚠️ Could not fetch ticket data: {e}")
                traceback.print_exc()
                # CRITICAL: Still use provided ticket_id to ensure chat separation
                resolved_ticket_id = ticket_id
                print(f"📋 Using provided ticket_id for group_id (resolution failed): {resolved_ticket_id}")
        else:
            print(f"⚠️ No ticket_id provided - messages will be in general private chat (not dispute-specific)")

        # Generate consistent group_id (include ticket_id to separate chats by dispute)
        # IMPORTANT: Always include ticket_id if provided, even if resolution failed
        chat_service = ChatService()
        group_id = chat_service._generate_private_group_id(caller_id, other_user_id_str, resolved_ticket_id)
        print(f"✅ Private chat group_id: {group_id} (ticket_id={resolved_ticket_id})")
        print(f"👤 Connection details: caller_id={caller_id}, other_user_id={other_user_id_str}, caller_role={caller_role}")
        print(f"🔑 Group ID generation: sorted([{caller_id}, {other_user_id_str}]) = {sorted([str(caller_id), str(other_user_id_str)])}")

        # Register connection with in-memory manager
        await websocket_manager.connect(websocket, caller_id, group_id)
        
        # Log current connections in this group after connection
        async with websocket_manager._lock:
            group_connections = len(websocket_manager.groups.get(group_id, set()))
            print(f"📊 Total connections in group {group_id}: {group_connections}")
            # List all connections in this group
            for ws in websocket_manager.groups.get(group_id, set()):
                meta = websocket_manager._ws_meta.get(ws, {})
                print(f"   - Connected user: {meta.get('user_id')} in group: {meta.get('group_id')}")

        # Send last N messages (filtered by ticket_id if provided)
        # IMPORTANT: Use resolved_ticket_id to ensure we only get messages for this specific dispute
        try:
            print(f"📜 Fetching private chat history: caller_id={caller_id}, other_user_id={other_user_id_str}, ticket_id={resolved_ticket_id}")
            history = chat_service.get_private_chat_history(caller_id, other_user_id_str, limit=100, ticket_id=resolved_ticket_id)
            print(f"📨 Found {len(history)} messages in history for this dispute")
            
            # Send history messages one by one with error handling
            sent_count = 0
            for h in history:
                try:
                    # Ensure message is JSON-serializable
                    if "_id" in h:
                        h["id"] = str(h["_id"])
                        h.pop("_id", None)
                    
                    # CRITICAL: Convert all datetime objects to timestamps
                    from datetime import datetime
                    if "created_at" in h and isinstance(h["created_at"], datetime):
                        h["timestamp"] = h["created_at"].isoformat() + "Z"
                        h["created_at"] = int(h["created_at"].timestamp())
                    if "updated_at" in h and isinstance(h["updated_at"], datetime):
                        h["updated_at"] = int(h["updated_at"].timestamp())
                    
                    # Remove any other datetime objects that might exist
                    for key, value in list(h.items()):
                        if isinstance(value, datetime):
                            h[key] = value.isoformat() + "Z"
                    
                    await websocket.send_json({"type": "history", "payload": h})
                    sent_count += 1
                except Exception as e:
                    print(f"⚠️ Error sending history message: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue with next message instead of failing completely
                    continue
            
            print(f"✅ Sent {sent_count}/{len(history)} history messages")
        except Exception as e:
            print(f"❌ ERROR fetching/sending chat history: {e}")
            traceback.print_exc()
            # Don't fail the connection - just log the error and continue
            # Send error message to client
            try:
                await websocket.send_json({"type": "error", "error": "Failed to load chat history. Please refresh."})
            except:
                pass

        # Main loop
        while True:
            data = await websocket.receive_json()
            content = (data.get("content") or "").strip()
            if not content:
                await websocket.send_json({"error": "Message cannot be empty"})
                continue

            # Save message - SIMPLIFIED: Just like group chat
            meta = {}
            if resolved_ticket_id:
                meta["ticket_id"] = resolved_ticket_id
            if project_id:
                meta["project_id"] = project_id
            if agreement_id:
                meta["agreement_id"] = agreement_id
            
            # Save message using the connection's group_id (same as group chat pattern)
            saved = chat_service.log_chat(
                group_type="private",
                request_id=None,
                group_id=group_id,  # Use the SAME group_id as the connection
                sender_user=caller,
                content=content,
                meta=meta
            )
            
            # Broadcast to group - EXACTLY like group chat
            payload = {
                "type": "message",
                "payload": {
                    "group_type": "private",
                    "group_id": group_id,
                    "message": saved,
                }
            }
            
            # Simple broadcast to group - just like agreement/project chat
            await websocket_manager.send_to_group(group_id, payload)

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