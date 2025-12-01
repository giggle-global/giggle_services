from typing import List, Optional, Dict, Any
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from app.core.db import database
from app.models.notification import NotificationStatus
from datetime import datetime
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

class NotificationRepository:
    def __init__(self):
        self.collection: Collection = database["notifications"]

    def create(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new notification"""
        try:
            notification_data["notification_id"] = uuid4().hex
            notification_data["status"] = NotificationStatus.UNREAD.value
            notification_data["created_at"] = int(datetime.utcnow().timestamp())
            notification_data["read_at"] = None
            self.collection.insert_one(notification_data)
            return notification_data
        except PyMongoError as e:
            logger.exception("Mongo error creating notification: %s", e)
            raise

    def get_by_id(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        try:
            return self.collection.find_one({"notification_id": notification_id}, {"_id": 0})
        except PyMongoError as e:
            logger.exception("Mongo error fetching notification: %s", e)
            raise

    def get_user_notifications(
        self, 
        user_id: str, 
        limit: int = 50, 
        skip: int = 0,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        try:
            query = {"user_id": user_id}
            if unread_only:
                query["status"] = NotificationStatus.UNREAD.value
            
            cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
            return list(cursor)
        except PyMongoError as e:
            logger.exception("Mongo error fetching user notifications: %s", e)
            raise

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user"""
        try:
            return self.collection.count_documents({
                "user_id": user_id,
                "status": NotificationStatus.UNREAD.value
            })
        except PyMongoError as e:
            logger.exception("Mongo error counting unread notifications: %s", e)
            raise

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        try:
            result = self.collection.update_one(
                {"notification_id": notification_id, "user_id": user_id},
                {
                    "$set": {
                        "status": NotificationStatus.READ.value,
                        "read_at": int(datetime.utcnow().timestamp())
                    }
                }
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.exception("Mongo error marking notification as read: %s", e)
            raise

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user"""
        try:
            result = self.collection.update_many(
                {
                    "user_id": user_id,
                    "status": NotificationStatus.UNREAD.value
                },
                {
                    "$set": {
                        "status": NotificationStatus.READ.value,
                        "read_at": int(datetime.utcnow().timestamp())
                    }
                }
            )
            return result.modified_count
        except PyMongoError as e:
            logger.exception("Mongo error marking all notifications as read: %s", e)
            raise

    def delete(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification"""
        try:
            result = self.collection.delete_one({
                "notification_id": notification_id,
                "user_id": user_id
            })
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.exception("Mongo error deleting notification: %s", e)
            raise

