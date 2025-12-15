# # -------------------
# # 📁 repositories/chat_repository.py
# # -------------------
# from app.core.db import database  # assumed existing Mongo client wrapper

# class ChatRepository:
#     def __init__(self):
#         self.collection = database["chat_messages"]

#     def save(self, chat_data: dict):
#         self.collection.insert_one(chat_data)

#     def get_history(self, project_id: str, type: str):
#         chat_history = list(self.collection.find({"project_id": project_id, "type": type}).sort("timestamp", 1))

#         for chat in chat_history:
#             chat.pop("_id", None)  # remove _id field entirely
#         return chat_history
    

# app/repositories/chat_repository.py
from typing import List, Dict, Any
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId
from app.core.db import database  # assumed existing Mongo client wrapper
from datetime import datetime

class ChatRepository:
    """
    Mongo-backed repository for storing group chat messages.
    Collection document structure (example):
    {
        "_id": ObjectId(...),
        "group_type": "project" | "agreement" | "private",
        "group_id": "<project_id or agreement_id or private::user1_id::user2_id>",
        "sender_id": "<user_id>",
        "sender_role": "<role>",
        "sender_name": "<first last>",
        "content": "<text>",
        "seen_by": ["user_id1", "user_id2"],     # optional
        "meta": { ... },                         # optional extra data (ticket_id, project_id, agreement_id for private chats)
        "created_at": ISODate,
        "updated_at": ISODate
    }
    """

    def __init__(self):
        self.col: Collection = database["group_chats"]
        # Ensure indexes
        self.col.create_index([("group_type", ASCENDING), ("group_id", ASCENDING), ("created_at", DESCENDING)])
        self.col.create_index([("group_id", ASCENDING), ("sender_id", ASCENDING), ("created_at", DESCENDING)])

    def save_message(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow()
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        res = self.col.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def get_history(self, group_type: str, request_id: str, limit: int = 100, before_iso: str = None) -> List[Dict[str, Any]]:
        if group_type == "project":
            q = {"group_type": "project", "group_id": request_id}
        elif group_type == "agreement":
            q = {"group_type": "agreement", "group_id": request_id}
        elif group_type == "private":
            q = {"group_type": "private", "group_id": request_id}
        else:
            raise ValueError("Invalid group_type, must be 'project', 'agreement', or 'private'")
        # Return most recent `limit` messages, ordered ascending by created_at (older -> newer)
        if before_iso:
            # allow client pagination; messages older than given timestamp
            from datetime import datetime
            q["created_at"] = {"$lt": datetime.fromisoformat(before_iso)}
        cursor = self.col.find(q).sort("created_at", ASCENDING).limit(limit)
        results = []
        for d in cursor:
            # Keep _id here; ChatService will convert it to a public `id` field
            results.append(d)
        return results

    def mark_seen(self, group_type: str, group_id: str, user_id: str) -> int:
        # Add user_id to seen_by array for all messages in the group that don't yet contain it
        res = self.col.update_many(
            {
                "group_type": group_type,
                "group_id": group_id,
                "seen_by": {"$ne": user_id}
            },
            {"$addToSet": {"seen_by": user_id}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return res.modified_count

    def get_unseen_count(self, group_type: str, group_id: str, user_id: str) -> int:
        return self.col.count_documents({
            "group_type": group_type,
            "group_id": group_id,
            "seen_by": {"$ne": user_id}
        })

    def get_unseen_conversation_count_for_user(self, user_id: str) -> int:
        """
        Count distinct **project conversations** (chats) that have at least one
        unread incoming message for the given user.

        Rules (WhatsApp-style):
        - Only include group_type == \"project\" (ignore private/admin + agreement chats)
        - Only count messages where:
            * sender_id != user_id   (message from the other party)
            * seen_by is missing OR does NOT contain user_id (treat legacy messages
              with no seen_by as unread until the user opens the chat)
        - Group by project_id (group_id) so each chat is counted once, no matter
          how many unread messages are inside it.
        """
        pipeline = [
            {
                "$match": {
                    "group_type": "project",
                    "sender_id": {"$ne": user_id},
                    "$or": [
                        {"seen_by": {"$exists": False}},
                        {"seen_by": {"$nin": [user_id]}},
                    ],
                }
            },
            {"$group": {"_id": "$group_id"}},
            {"$count": "conversation_count"},
        ]
        try:
            result = list(self.col.aggregate(pipeline))
            if not result:
                return 0
            return int(result[0].get("conversation_count", 0))
        except Exception:
            # Fail-safe: don't break if aggregation fails
            return 0
