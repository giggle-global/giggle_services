# -------------------
# 📁 services/chat_service.py
# -------------------
from app.repositories.chat import ChatRepository
from datetime import datetime

class ChatService:
    def __init__(self):
        self.repo = ChatRepository()

    def log_chat(self, project_id, user_id, message, role, user_name):
        chat_entry = {
            "project_id": project_id,
            "user_id": user_id,
            "message": message,
            "role": role,
            "user_name": user_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.repo.save(chat_entry)

    def get_chat_history(self, project_id):
        return self.repo.get_history(project_id)


class WebSocketManager:
    def __init__(self):
        self.connections = {}  # user_id: websocket
        self.groups = {}       # project_id: set(user_ids)

    async def connect(self, user_id, project_id, websocket):
        self.connections[user_id] = websocket
        self.groups.setdefault(project_id, set()).add(user_id)

    async def disconnect(self, user_id, project_id):
        self.connections.pop(user_id, None)
        if project_id in self.groups:
            self.groups[project_id].discard(user_id)

    async def send_to_group(self, project_id, message: dict):
        for uid in self.groups.get(project_id, []):
            if uid in self.connections:
                await self.connections[uid].send_json(message)