# -------------------
# 📁 repositories/chat_repository.py
# -------------------
from app.core.db import database  # assumed existing Mongo client wrapper

class ChatRepository:
    def __init__(self):
        self.collection = database["chat_messages"]

    def save(self, chat_data: dict):
        self.collection.insert_one(chat_data)

    def get_history(self, project_id: str):
        chat_history = list(self.collection.find({"project_id": project_id}).sort("timestamp", 1))
    
        for chat in chat_history:
            chat.pop("_id", None)  # remove _id field entirely
        return chat_history