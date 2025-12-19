# # -------------------
# # 📁 services/chat_service.py
# # -------------------
# from app.repositories.chat import ChatRepository
# from datetime import datetime

# class ChatService:
#     def __init__(self):
#         self.repo = ChatRepository()

#     def log_chat(self, type, project_id, user_id, message, role, first_name, last_name):
#         chat_entry = {
#             "type": type,
#             "project_id": project_id,
#             "user_id": user_id, 
#             "message": message,
#             "role": role,
#             "user_name": first_name + " " + last_name,
#             "timestamp": datetime.utcnow().isoformat()
#         }
#         self.repo.save(chat_entry)

#     def get_chat_history(self, project_id, type):
#         return self.repo.get_history(project_id, type)


# class WebSocketManager:
#     def __init__(self):
#         self.connections = {}  # user_id: websocket
#         self.groups = {}       # project_id: set(user_ids)

#     async def connect(self, user_id, project_id, websocket):
#         self.connections[user_id] = websocket
#         self.groups.setdefault(project_id, set()).add(user_id)

#     async def disconnect(self, user_id, project_id):
#         self.connections.pop(user_id, None)
#         if project_id in self.groups:
#             self.groups[project_id].discard(user_id)

#     async def send_to_group(self, project_id, message: dict):
#         for uid in self.groups.get(project_id, []):
#             if uid in self.connections:
#                 await self.connections[uid].send_json(message)


# app/services/chat.py
import asyncio
import re
from typing import Dict, Any, Set, Tuple, List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import WebSocket
from app.repositories.chat import ChatRepository
from pymongo import DESCENDING, ASCENDING

# Simple WebSocket manager supporting group broadcast and per-user connection tracking
class WebSocketManager:
    def __init__(self):
        # group_id -> set of websockets
        self.groups: Dict[str, Set[WebSocket]] = {}
        # ws -> (user_id, group_id) for cleanup
        self._ws_meta: Dict[WebSocket, Dict[str,str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, group_id: str):
        async with self._lock:
            if group_id not in self.groups:
                self.groups[group_id] = set()
            self.groups[group_id].add(websocket)
            self._ws_meta[websocket] = {"user_id": user_id, "group_id": group_id}

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            meta = self._ws_meta.pop(websocket, None)
            if not meta:
                return
            group_id = meta.get("group_id")
            if group_id and group_id in self.groups:
                self.groups[group_id].discard(websocket)
                if not self.groups[group_id]:
                    # optional: delete empty group set
                    del self.groups[group_id]

    async def send_to_group(self, group_id: str, payload: Dict[str, Any]):
        # Best-effort broadcasting: remove dead websockets
        to_remove = []
        conns = []
        async with self._lock:
            conns = list(self.groups.get(group_id, set()))
            print(f"📤 send_to_group: group_id={group_id}, connections={len(conns)}")
            for ws in conns:
                meta = self._ws_meta.get(ws, {})
                print(f"   - Sending to user: {meta.get('user_id')} in group: {meta.get('group_id')}")
        
        sent_count = 0
        for ws in conns:
            try:
                await ws.send_json(payload)
                sent_count += 1
                print(f"   ✅ Successfully sent to connection")
            except Exception as e:
                print(f"   ❌ Failed to send to connection: {e}")
                # schedule removal
                to_remove.append(ws)
        
        print(f"📤 Sent to {sent_count}/{len(conns)} connections in group {group_id}")
        
        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    self.groups.get(group_id, set()).discard(ws)
                    self._ws_meta.pop(ws, None)

    async def send_to_user(self, user_id: str, payload: Dict[str, Any], target_group_id: Optional[str] = None):
        """
        Send message to a specific user's connection(s).
        Used for private chats where we need to find the user's websocket.
        If target_group_id is provided, only send to connections in that specific group.
        """
        to_remove = []
        conns = []
        async with self._lock:
            # Find websockets for this user, optionally filtered by group_id
            print(f"🔍 send_to_user: Looking for user_id={user_id}, target_group_id={target_group_id}")
            for ws, meta in self._ws_meta.items():
                meta_user_id = meta.get("user_id")
                meta_group_id = meta.get("group_id")
                if meta_user_id == user_id:
                    # If target_group_id is specified, only send to that group
                    if target_group_id:
                        if meta_group_id == target_group_id:
                            print(f"   ✅ Found matching connection: user_id={meta_user_id}, group_id={meta_group_id}")
                            conns.append(ws)
                        else:
                            print(f"   ⚠️ Skipping connection - group_id mismatch: user_id={meta_user_id}, group_id={meta_group_id} (expected {target_group_id})")
                    else:
                        # If no target_group_id, send to all user's connections (backward compatibility)
                        print(f"   ✅ Found connection (no group filter): user_id={meta_user_id}, group_id={meta_group_id}")
                        conns.append(ws)
        
        print(f"📤 Sending to {len(conns)} connection(s) for user_id={user_id}")
        for ws in conns:
            try:
                await ws.send_json(payload)
                print(f"   ✅ Successfully sent to connection")
            except Exception as e:
                print(f"   ❌ Failed to send to connection: {e}")
                to_remove.append(ws)
        
        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    meta = self._ws_meta.pop(ws, None)
                    if meta:
                        group_id = meta.get("group_id")
                        if group_id and group_id in self.groups:
                            self.groups[group_id].discard(ws)
                            if not self.groups[group_id]:
                                del self.groups[group_id]


class ChatService:
    def __init__(self):
        self.repo = ChatRepository()

    def _build_sender_name(self, user: Dict[str, Any]) -> str:
        return ((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip()

    def _utc_to_iso(self, dt: datetime) -> str:
        """
        Convert a UTC datetime object to ISO 8601 string in UTC.
        The browser will then render this as the user's local time.
        """
        # Ensure we're working with UTC datetime
        if dt.tzinfo is None:
            # Naive datetime is assumed to be UTC
            return dt.isoformat() + "Z"
        else:
            # Convert to UTC if timezone-aware
            utc_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return utc_dt.isoformat() + "Z"

    def log_chat(self, group_type: str, request_id: Optional[str], group_id: str, sender_user: Dict[str, Any], content: str, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Persist chat message to DB and return the saved document (without _id).
        sender_user is the full user dict (with id, role, first_name, last_name)
        """
        doc = {
            "group_type": group_type,
            "group_id": group_id,
            "request_id": request_id if request_id is not None else "",
            "sender_id": sender_user.get("id") or sender_user.get("user_id") or sender_user.get("sub"),
            "sender_role": sender_user.get("role"),
            "sender_name": self._build_sender_name(sender_user),
            "content": content,
            "seen_by": [sender_user.get("id") or sender_user.get("user_id") or sender_user.get("sub")],
            "meta": meta or {}
        }
        saved = self.repo.save_message(doc)

        # Expose a stable string id for frontend de‑duplication,
        # while not leaking raw Mongo ObjectId field name.
        if "_id" in saved:
            saved["id"] = str(saved["_id"])
            saved.pop("_id", None)

        # Convert created_at datetime to Unix timestamp for JSON serialization
        created_val = saved.get("created_at")
        if isinstance(created_val, datetime):
            # Convert datetime to Unix timestamp (seconds since epoch)
            # Store timestamp before converting
            saved["timestamp"] = self._utc_to_iso(created_val)
            saved["created_at"] = int(created_val.timestamp())
        elif isinstance(created_val, (int, float)):
            # Already a timestamp, ensure it's an int
            saved["created_at"] = int(created_val)
            saved["timestamp"] = self._utc_to_iso(datetime.utcfromtimestamp(created_val))
        else:
            # Fallback: use current UTC time
            now = datetime.utcnow()
            saved["timestamp"] = self._utc_to_iso(now)
            saved["created_at"] = int(now.timestamp())
        
        # Also convert updated_at if present
        updated_val = saved.get("updated_at")
        if isinstance(updated_val, datetime):
            saved["updated_at"] = int(updated_val.timestamp())
        elif isinstance(updated_val, (int, float)):
            saved["updated_at"] = int(updated_val)
        
        return saved
    
    def get_history_before(self, group_type: str, group_id: str, before: Optional[int], limit: int = 30) -> Tuple[List[dict], bool, Optional[int]]:
        """
        Returns (messages, has_more, next_before)
        - messages: list of messages ordered oldest -> newest (for client prepending)
        - has_more: True if there are older messages available
        - next_before: epoch to use for next load_more (e.g., messages[0]['created_at'])
        """
        # If before not provided, treat as "latest" (fetch most recent)
        if before is None:
            # use a very large number so query gets newest messages
            before = 2**62

        # Query: created_at < before (strictly older), sorted newest first, limit N+1 to detect has_more
        docs = list(self.repo.col.find(
            {"group_type": group_type, "group_id": group_id, "created_at": {"$lt": before}}
        ).sort("created_at", DESCENDING).limit(limit + 1))

        # We fetched newest->oldest; convert to oldest->newest for client
        has_more = len(docs) > limit
        if has_more:
            docs = docs[:-1]  # drop the extra record used to detect has_more

        # reverse for chronological order oldest -> newest
        docs = list(reversed(docs))

        # make JSON safe if necessary (you said timestamps are epoch ints, ObjectId -> str)
        for d in docs:
            if "_id" in d:
                # Expose stable id field and hide raw Mongo key
                d["id"] = str(d["_id"])
                d.pop("_id", None)
            # Convert datetime to Unix timestamp and add UTC timestamp for frontend display
            if "created_at" in d:
                # Handle both datetime objects and Unix timestamps
                if isinstance(d["created_at"], datetime):
                    # Store timestamp before converting
                    d["timestamp"] = self._utc_to_iso(d["created_at"])
                    d["created_at"] = int(d["created_at"].timestamp())
                elif isinstance(d["created_at"], (int, float)):
                    d["created_at"] = int(d["created_at"])
                    d["timestamp"] = self._utc_to_iso(datetime.utcfromtimestamp(d["created_at"]))
                else:
                    now = datetime.utcnow()
                    d["timestamp"] = self._utc_to_iso(now)
                    d["created_at"] = int(now.timestamp())
            
            # Also convert updated_at if present
            if "updated_at" in d and isinstance(d["updated_at"], datetime):
                d["updated_at"] = int(d["updated_at"].timestamp())

        next_before = docs[0]["created_at"] if docs else None
        return docs, has_more, next_before

    def get_chat_history(self, group_type: str, group_id: str, limit: int = 100, before_iso: str = None):
        history = self.repo.get_history(group_type, group_id, limit=limit, before_iso=before_iso)
        # Add UTC timestamp to each message for frontend display
        for msg in history:
            # Ensure id field is present for de‑duplication on the client
            if "_id" in msg:
                msg["id"] = str(msg["_id"])
                msg.pop("_id", None)
            # Convert datetime to Unix timestamp and add UTC timestamp for frontend display
            if "created_at" in msg:
                # Handle both datetime objects and Unix timestamps
                if isinstance(msg["created_at"], datetime):
                    # Store timestamp before converting
                    msg["timestamp"] = self._utc_to_iso(msg["created_at"])
                    msg["created_at"] = int(msg["created_at"].timestamp())
                elif isinstance(msg["created_at"], (int, float)):
                    msg["created_at"] = int(msg["created_at"])
                    msg["timestamp"] = self._utc_to_iso(datetime.utcfromtimestamp(msg["created_at"]))
                else:
                    now = datetime.utcnow()
                    msg["timestamp"] = self._utc_to_iso(now)
                    msg["created_at"] = int(now.timestamp())
            
            # Also convert updated_at if present
            if "updated_at" in msg and isinstance(msg["updated_at"], datetime):
                msg["updated_at"] = int(msg["updated_at"].timestamp())
        return history

    def mark_seen(self, group_type: str, group_id: str, user_id: str) -> int:
        return self.repo.mark_seen(group_type, group_id, user_id)

    def get_unseen_count(self, group_type: str, group_id: str, user_id: str) -> int:
        return self.repo.get_unseen_count(group_type, group_id, user_id)

    def get_unseen_conversation_count_for_user(self, user_id: str) -> int:
        """
        Return the number of distinct conversations (group_type + group_id)
        that have at least one unseen message for the given user.
        """
        return self.repo.get_unseen_conversation_count_for_user(user_id)

    def _generate_private_group_id(self, user1_id: str, user2_id: str, ticket_id: Optional[str] = None, agreement_id: Optional[str] = None) -> str:
        """
        Generate consistent group_id for private chat by sorting user IDs.
        If ticket_id is provided, include it to separate chats by dispute.
        If agreement_id is provided, include it to separate chats by agreement.
        This ensures both users see the same conversation regardless of who initiated,
        and each dispute/agreement has its own separate private chat.
        """
        sorted_ids = sorted([str(user1_id), str(user2_id)])
        if ticket_id:
            return f"private::{sorted_ids[0]}::{sorted_ids[1]}::ticket::{ticket_id}"
        if agreement_id:
            return f"private::{sorted_ids[0]}::{sorted_ids[1]}::agreement::{agreement_id}"
        return f"private::{sorted_ids[0]}::{sorted_ids[1]}"

    def log_private_chat(
        self,
        admin_id: str,
        other_user_id: str,
        sender_user: Dict[str, Any],
        content: str,
        ticket_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agreement_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save private chat message between admin and another user (client or freelancer).
        If ticket_id is provided, the chat will be separated by dispute.
        If agreement_id is provided, the chat will be separated by agreement.
        """
        group_id = self._generate_private_group_id(admin_id, other_user_id, ticket_id, agreement_id)
        meta = {}
        if ticket_id:
            meta["ticket_id"] = ticket_id
        if project_id:
            meta["project_id"] = project_id
        if agreement_id:
            meta["agreement_id"] = agreement_id
        
        return self.log_chat(
            group_type="private",
            request_id=None,  # Private chats don't have request_id
            group_id=group_id,
            sender_user=sender_user,
            content=content,
            meta=meta
        )

    def get_private_chat_history(self, user1_id: str, user2_id: str, limit: int = 100, ticket_id: Optional[str] = None, agreement_id: Optional[str] = None):
        """
        Get private chat history between two users.
        If ticket_id is provided, returns history for that specific dispute only.
        If agreement_id is provided, returns history for that specific agreement only.
        FIXED: Also fetches messages with different ticket_id formats to handle mismatches.
        """
        # Generate group_id - prioritize ticket_id over agreement_id if both are provided
        group_id = self._generate_private_group_id(user1_id, user2_id, ticket_id, agreement_id)
        print(f"🔍 get_private_chat_history: user1={user1_id}, user2={user2_id}, ticket_id={ticket_id}, agreement_id={agreement_id}, group_id={group_id}")
        
        # First, try to get messages with exact group_id
        query = {"group_type": "private", "group_id": group_id}
        direct_count = self.repo.col.count_documents(query)
        print(f"🔍 Direct DB query count for group_id={group_id}: {direct_count} messages")
        
        history = self.get_chat_history("private", group_id, limit=limit)
        
        # CRITICAL FIX: If ticket_id or agreement_id is provided, ONLY fetch messages for that specific ticket/agreement
        # Only check for alternative formats if we have very few messages (handles ticket_id/agreement_id format mismatch)
        if (ticket_id or agreement_id) and len(history) < 5:
            try:
                filter_type = 'ticket_id' if ticket_id else 'agreement_id'
                filter_value = ticket_id or agreement_id
                print(f"⚠️ Few messages found ({len(history)}) for {filter_type}={filter_value}. Checking for messages with different formats for THIS {filter_type} only...")
                
                sorted_ids = sorted([str(user1_id), str(user2_id)])
                base_pattern = f"private::{sorted_ids[0]}::{sorted_ids[1]}"
                
                # Escape special regex characters in the pattern
                escaped_pattern = re.escape(base_pattern)
                
                # Build alternative query based on whether we're looking for ticket_id or agreement_id
                if ticket_id:
                    # CRITICAL: Only match messages that contain THIS ticket_id (case-insensitive)
                    # Match patterns like: private::user1::user2::ticket::TICKET_ID (any case variation)
                    ticket_id_upper = ticket_id.upper()
                    ticket_pattern = f"{escaped_pattern}::ticket::.*{re.escape(ticket_id_upper)}"
                    
                    alternative_query = {
                        "group_type": "private",
                        "$or": [
                            # Match group_id with this ticket_id (case-insensitive)
                            {"group_id": {"$regex": ticket_pattern, "$options": "i"}},
                            # OR match meta.ticket_id field (case-insensitive)
                            {"meta.ticket_id": {"$regex": f"^{re.escape(ticket_id_upper)}$", "$options": "i"}}
                        ]
                    }
                elif agreement_id:
                    # CRITICAL: Only match messages that contain THIS agreement_id
                    # Match patterns like: private::user1::user2::agreement::AGREEMENT_ID
                    agreement_pattern = f"{escaped_pattern}::agreement::.*{re.escape(agreement_id)}"
                    
                    alternative_query = {
                        "group_type": "private",
                        "$or": [
                            # Match group_id with this agreement_id
                            {"group_id": {"$regex": agreement_pattern, "$options": "i"}},
                            # OR match meta.agreement_id field
                            {"meta.agreement_id": agreement_id}
                        ]
                    }
                else:
                    alternative_query = None
                
                if alternative_query:
                    alternative_messages = list(self.repo.col.find(alternative_query).sort("created_at", DESCENDING).limit(limit))
                    filter_type = 'ticket_id' if ticket_id else 'agreement_id'
                    print(f"🔍 Found {len(alternative_messages)} messages with alternative {filter_type} formats for THIS {filter_type} only")
                    
                    # Merge and deduplicate messages - ONLY include messages for THIS ticket/agreement
                    existing_ids = {msg.get("id") or str(msg.get("_id", "")) for msg in history}
                    for alt_msg in alternative_messages:
                        try:
                            # CRITICAL: Double-check this message is for the correct ticket/agreement
                            alt_group_id = alt_msg.get("group_id", "")
                            alt_meta = alt_msg.get("meta", {})
                            alt_meta_ticket = alt_meta.get("ticket_id", "")
                            alt_meta_agreement = alt_meta.get("agreement_id", "")
                            
                            # Verify this message belongs to the requested ticket/agreement
                            matches = False
                            if ticket_id:
                                ticket_id_upper = ticket_id.upper()
                                if ticket_id_upper in alt_group_id.upper():
                                    matches = True
                                elif alt_meta_ticket and alt_meta_ticket.upper() == ticket_id_upper:
                                    matches = True
                                elif alt_meta_ticket and ticket_id_upper in alt_meta_ticket.upper():
                                    matches = True
                            elif agreement_id:
                                if agreement_id in alt_group_id:
                                    matches = True
                                elif alt_meta_agreement == agreement_id:
                                    matches = True
                            
                            if not matches:
                                print(f"   ⚠️ Skipping message - {filter_type} mismatch: group_id={alt_group_id}, meta={alt_meta}")
                                continue
                            
                            alt_id = alt_msg.get("id") or str(alt_msg.get("_id", ""))
                            if alt_id not in existing_ids:
                                # Convert datetime to timestamp if needed
                                if "created_at" in alt_msg:
                                    if isinstance(alt_msg["created_at"], datetime):
                                        alt_msg["timestamp"] = self._utc_to_iso(alt_msg["created_at"])
                                        alt_msg["created_at"] = int(alt_msg["created_at"].timestamp())
                                    elif isinstance(alt_msg["created_at"], (int, float)):
                                        alt_msg["created_at"] = int(alt_msg["created_at"])
                                        alt_msg["timestamp"] = self._utc_to_iso(datetime.utcfromtimestamp(alt_msg["created_at"]))
                                    else:
                                        # Fallback: use current time
                                        now = datetime.utcnow()
                                        alt_msg["timestamp"] = self._utc_to_iso(now)
                                        alt_msg["created_at"] = int(now.timestamp())
                                
                                # Convert updated_at if present
                                if "updated_at" in alt_msg and isinstance(alt_msg["updated_at"], datetime):
                                    alt_msg["updated_at"] = int(alt_msg["updated_at"].timestamp())
                                
                                # Remove any other datetime objects that might exist
                                for key, value in list(alt_msg.items()):
                                    if isinstance(value, datetime) and key not in ["created_at", "updated_at"]:
                                        alt_msg[key] = value.isoformat() + "Z"
                                
                                # Add id field
                                if "_id" in alt_msg:
                                    alt_msg["id"] = str(alt_msg["_id"])
                                    alt_msg.pop("_id", None)
                                
                                history.append(alt_msg)
                                existing_ids.add(alt_id)
                        except Exception as e:
                            print(f"⚠️ Error processing alternative message: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    
                    # Sort by created_at
                    history.sort(key=lambda x: x.get("created_at", 0))
                    print(f"📬 Total messages after merging: {len(history)}")
            except Exception as e:
                print(f"⚠️ Error fetching alternative messages (non-critical): {e}")
                import traceback
                traceback.print_exc()
                # Continue with original history - this is a fallback, so don't fail
        
        # CRITICAL: Filter to ensure ONLY messages for this specific ticket/agreement are returned
        # This prevents showing messages from other tickets/agreements
        if ticket_id or agreement_id:
            filtered_history = []
            ticket_id_upper = ticket_id.upper() if ticket_id else None
            agreement_id_str = agreement_id if agreement_id else None
            for msg in history:
                msg_group_id = msg.get("group_id", "")
                msg_meta_ticket = msg.get("meta", {}).get("ticket_id", "")
                msg_meta_agreement = msg.get("meta", {}).get("agreement_id", "")
                
                # Include message if it matches this ticket_id or agreement_id
                matches = False
                if ticket_id_upper:
                    if ticket_id_upper in msg_group_id.upper() or \
                       (msg_meta_ticket and msg_meta_ticket.upper() == ticket_id_upper) or \
                       (msg_meta_ticket and ticket_id_upper in msg_meta_ticket.upper()):
                        matches = True
                if agreement_id_str and not matches:
                    if agreement_id_str == msg_meta_agreement:
                        matches = True
                
                if matches:
                    filtered_history.append(msg)
                else:
                    print(f"   ⚠️ Filtered out message - wrong ticket/agreement: group_id={msg_group_id}, meta.ticket_id={msg_meta_ticket}, meta.agreement_id={msg_meta_agreement}")
            
            history = filtered_history
            filter_type = 'ticket_id' if ticket_id else 'agreement_id' if agreement_id else 'none'
            filter_value = ticket_id or agreement_id
            print(f"📬 After {filter_type} filtering: {len(history)} messages for {filter_type}={filter_value}")
        
        print(f"📬 Retrieved {len(history)} messages for group_id={group_id}")
        
        # Log first few messages if any
        if history:
            print(f"📬 First message: sender={history[0].get('sender_id')}, group_id={history[0].get('group_id')}")
            print(f"📬 Last message: sender={history[-1].get('sender_id')}, group_id={history[-1].get('group_id')}")
        else:
            print(f"⚠️ No messages found in history. Checking all private messages for these users...")
            # Check all private messages between these users
            all_private = list(self.repo.col.find({
                "group_type": "private",
                "$or": [
                    {"sender_id": str(user1_id)},
                    {"sender_id": str(user2_id)}
                ]
            }).limit(10))
            print(f"🔍 Found {len(all_private)} total private messages involving these users")
            for msg in all_private[:3]:
                print(f"   - Message group_id: {msg.get('group_id')}, sender: {msg.get('sender_id')}, content: {msg.get('content', '')[:50]}")
        
        return history
