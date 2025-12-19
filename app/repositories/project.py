from typing import Optional, List, Dict, Any
from pymongo.collection import Collection
from app.core.db import database

class ProjectRepository:
    def __init__(self):
        self.collection: Collection = database["projects"]

    def insert(self, doc: Dict[str, Any]) -> None:
        self.collection.insert_one(doc)

    def find_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({"id": project_id}, {"_id": 0})

    def find_all(self) -> List[Dict[str, Any]]:
        return list(self.collection.find({}, {"_id": 0}))

    def update(self, project_id: str, update_data: Dict[str, Any]) -> int:
        result = self.collection.update_one({"id": project_id}, {"$set": update_data})
        return result.matched_count

    def update_status(self, project_id: str, status: str) -> int:
        result = self.collection.update_one({"id": project_id}, {"$set": {"status": status}})
        return result.matched_count

    def delete(self, project_id: str) -> int:
        result = self.collection.delete_one({"id": project_id})
        return result.deleted_count

    def find_similar(
        self,
        industry: Optional[str] = None,
        background: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if industry:
            query["industry"] = industry
        if background:
            query["background_industry"] = background
        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return list(cursor)

    def find_recent_projects(self, hours: int = 24, limit: int = 20, created_by: Optional[list[str]] = None) -> List[Dict[str, Any]]:
        """Find projects created within the last N hours, only enabled projects
        Note: Projects are stored with UTC timestamps, but we calculate the cutoff
        based on IST (UTC+5:30) to match user expectations in India.
        """
        from datetime import datetime, timedelta, timezone
        # IST is UTC+5:30
        ist_offset = timedelta(hours=5, minutes=30)
        ist_timezone = timezone(ist_offset)
        
        # Get current time in IST
        now_ist = datetime.now(ist_timezone)
        
        # Calculate cutoff time in IST (N hours ago)
        cutoff_ist = now_ist - timedelta(hours=hours)
        
        # Convert IST cutoff time back to UTC for database query
        # Since created_at is stored in UTC, we need to convert the IST cutoff to UTC
        cutoff_utc = cutoff_ist.astimezone(timezone.utc)
        cutoff_time = int(cutoff_utc.timestamp())
        
        query: Dict[str, Any] = {
            "status": "enabled",
            "created_at": {"$exists": True, "$gte": cutoff_time}
        }
        if created_by:
            # Allow both created_by and client_id matches to support legacy data
            query["$or"] = [
                {"created_by": {"$in": created_by}},
                {"client_id": {"$in": created_by}},
            ]
        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return list(cursor)