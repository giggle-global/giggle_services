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
