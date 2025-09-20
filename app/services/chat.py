# -------------------
# 📁 services/chat_service.py
# -------------------
from app.repositories.chat import ChatRepository
from datetime import datetime

class ChatService:
    def __init__(self):
        self.repo = ChatRepository()

    def log_chat(self, type, project_id, user_id, message, role, first_name, last_name):
        chat_entry = {
            "type": type,
            "project_id": project_id,
            "user_id": user_id,
            "message": message,
            "role": role,
            "user_name": first_name + " " + last_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.repo.save(chat_entry)

    def get_chat_history(self, project_id, type):
        return self.repo.get_history(project_id, type)


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