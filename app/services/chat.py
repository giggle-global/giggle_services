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
from typing import Dict, Any, Set, Tuple, List, Optional
from datetime import datetime
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
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                # schedule removal
                to_remove.append(ws)
        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    self.groups.get(group_id, set()).discard(ws)
                    self._ws_meta.pop(ws, None)


class ChatService:
    def __init__(self):
        self.repo = ChatRepository()

    def _build_sender_name(self, user: Dict[str, Any]) -> str:
        return ((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip()

    def log_chat(self, group_type: str, request_id: str, group_id: str, sender_user: Dict[str, Any], content: str, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Persist chat message to DB and return the saved document (without _id).
        sender_user is the full user dict (with id, role, first_name, last_name)
        """
        doc = {
            "group_type": group_type,
            "group_id": group_id,
            "request_id": request_id,
            "sender_id": sender_user.get("id") or sender_user.get("user_id") or sender_user.get("sub"),
            "sender_role": sender_user.get("role"),
            "sender_name": self._build_sender_name(sender_user),
            "content": content,
            "seen_by": [sender_user.get("id") or sender_user.get("user_id") or sender_user.get("sub")],
            "meta": meta or {},
            "created_at": int(datetime.utcnow().timestamp()),
            "updated_at": int(datetime.utcnow().timestamp())
        }
        saved = self.repo.save_message(doc)
        # Remove _id before returning to caller (router will not expose DB internal IDs)
        saved.pop("_id", None)
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
                d["_id"] = str(d["_id"])
            # created_at already int; if not, convert here

        next_before = docs[0]["created_at"] if docs else None
        return docs, has_more, next_before

    def get_chat_history(self, group_type: str, request_id: str, limit: int = 100, before_iso: str = None):
        return self.repo.get_history(group_type, request_id, limit=limit, before_iso=before_iso)

    def mark_seen(self, group_type: str, request_id: str, user_id: str) -> int:
        return self.repo.mark_seen(group_type, request_id, user_id)

    def get_unseen_count(self, group_type: str, request_id: str, user_id: str) -> int:
        return self.repo.get_unseen_count(group_type, request_id, user_id)
