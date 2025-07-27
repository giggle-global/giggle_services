from app.repositories.chat import ChatRepository
from app.models.chat import MessageIn, MessageOut
from typing import List

class ChatService:
    def __init__(self, repo: ChatRepository):
        self.repo = repo

    async def send_message(self, client_id: str, freelancer_id: str, sender_id: str, sender_role: str, message: str):
        chat_id = await self.repo.get_or_create_chat(client_id, freelancer_id)
        return await self.repo.add_message(chat_id, sender_id, sender_role, message)

    async def mark_all_seen(self, chat_id: str, user_id: str):
        await self.repo.mark_seen(chat_id, user_id)

    async def get_chat_messages(self, chat_id: str, skip: int, limit: int) -> List[MessageOut]:
        messages = await self.repo.get_messages(chat_id, skip, limit)
        return [MessageOut(**msg.dict()) for msg in messages]

    async def get_unread_message_count(self, chat_id: str, user_id: str) -> int:
        return await self.repo.count_unread(chat_id, user_id)

