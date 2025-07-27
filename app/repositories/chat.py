from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from app.models.chat import ChatSession, Message
from datetime import datetime

class ChatRepository:
    def __init__(self, chat_collection: AsyncIOMotorCollection, message_collection: AsyncIOMotorCollection):
        self.chat_collection = chat_collection
        self.message_collection = message_collection

    async def get_or_create_chat(self, client_id: str, freelancer_id: str) -> str:
        chat = await self.chat_collection.find_one({"client_id": client_id, "freelancer_id": freelancer_id})
        if chat:
            return str(chat["_id"])
        result = await self.chat_collection.insert_one({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "created_at": datetime.utcnow(),
            "last_updated": datetime.utcnow()
        })
        return str(result.inserted_id)

    async def add_message(self, chat_id: str, sender_id: str, sender_role: str, message: str) -> str:
        msg = {
            "chat_id": chat_id,
            "sender_id": sender_id,
            "sender_role": sender_role,
            "message": message,
            "timestamp": datetime.utcnow(),
            "seen_by": []
        }
        result = await self.message_collection.insert_one(msg)
        await self.chat_collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": {"last_updated": datetime.utcnow()}}
        )
        return str(result.inserted_id)

    async def mark_seen(self, chat_id: str, user_id: str):
        await self.message_collection.update_many(
            {"chat_id": chat_id, "seen_by": {"$ne": user_id}},
            {"$addToSet": {"seen_by": user_id}}
        )

    async def get_messages(self, chat_id: str, skip: int, limit: int):
        cursor = self.message_collection.find({"chat_id": chat_id}).sort("timestamp", -1).skip(skip).limit(limit)
        return [Message(**doc) async for doc in cursor]
    

    async def count_unread(self, chat_id: str, user_id: str) -> int:
        return await self.message_collection.count_documents({
            "chat_id": chat_id,
            "seen_by": {"$ne": user_id}
        })
