"""
Meeting repository for database operations
"""
import uuid
from typing import Dict, Any, List, Optional
from pymongo.collection import Collection
from pymongo import ReturnDocument, DESCENDING, ASCENDING
from app.core.db import database
from app.models.meeting import MeetingStatus
from datetime import datetime


class MeetingRepository:
    """Repository for meeting database operations"""
    
    def __init__(self):
        self.collection: Collection = database["meetings"]
    
    def create(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new meeting"""
        meeting_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())
        
        doc = {
            "meeting_id": meeting_id,
            "agreement_id": meeting_data["agreement_id"],
            "title": meeting_data["title"],
            "description": meeting_data.get("description"),
            "scheduled_time": meeting_data["scheduled_time"],
            "duration_minutes": meeting_data["duration_minutes"],
            "timezone": meeting_data.get("timezone", "UTC"),
            "status": meeting_data.get("status", MeetingStatus.SCHEDULED.value),
            "google_meet_link": meeting_data.get("google_meet_link"),
            "google_calendar_event_id": meeting_data.get("google_calendar_event_id"),
            "client": meeting_data["client"],
            "freelancer": meeting_data["freelancer"],
            "created_by": meeting_data["created_by"],
            "created_at": now,
            "updated_at": now,
            "cancelled_at": None,
            "cancelled_by": None
        }
        
        self.collection.insert_one(doc)
        return doc
    
    def get_by_id(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting by ID"""
        return self.collection.find_one({"meeting_id": meeting_id}, {"_id": 0})
    
    def get_by_agreement(self, agreement_id: str, upcoming_only: bool = False) -> List[Dict[str, Any]]:
        """Get all meetings for an agreement"""
        query = {"agreement_id": agreement_id}
        
        if upcoming_only:
            now = int(datetime.utcnow().timestamp())
            query["scheduled_time"] = {"$gte": now}
            query["status"] = {"$in": [MeetingStatus.SCHEDULED.value, MeetingStatus.ONGOING.value]}
        
        return list(self.collection.find(query, {"_id": 0}).sort("scheduled_time", ASCENDING))
    
    def get_by_user(self, user_id: str, upcoming_only: bool = False) -> List[Dict[str, Any]]:
        """Get all meetings for a user (as client or freelancer)"""
        query = {
            "$or": [
                {"client.user_id": user_id},
                {"freelancer.user_id": user_id}
            ]
        }
        
        if upcoming_only:
            now = int(datetime.utcnow().timestamp())
            query["scheduled_time"] = {"$gte": now}
            query["status"] = {"$in": [MeetingStatus.SCHEDULED.value, MeetingStatus.ONGOING.value]}
        
        return list(self.collection.find(query, {"_id": 0}).sort("scheduled_time", ASCENDING))
    
    def update(self, meeting_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a meeting"""
        update_data["updated_at"] = int(datetime.utcnow().timestamp())
        
        result = self.collection.find_one_and_update(
            {"meeting_id": meeting_id},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        
        return result
    
    def cancel(self, meeting_id: str, cancelled_by: str) -> Optional[Dict[str, Any]]:
        """Cancel a meeting"""
        now = int(datetime.utcnow().timestamp())
        
        result = self.collection.find_one_and_update(
            {"meeting_id": meeting_id},
            {
                "$set": {
                    "status": MeetingStatus.CANCELLED.value,
                    "cancelled_at": now,
                    "cancelled_by": cancelled_by,
                    "updated_at": now
                }
            },
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        
        return result
    
    def get_upcoming_meetings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming meetings across all agreements"""
        now = int(datetime.utcnow().timestamp())
        
        query = {
            "scheduled_time": {"$gte": now},
            "status": {"$in": [MeetingStatus.SCHEDULED.value, MeetingStatus.ONGOING.value]}
        }
        
        return list(
            self.collection.find(query, {"_id": 0})
            .sort("scheduled_time", ASCENDING)
            .limit(limit)
        )


