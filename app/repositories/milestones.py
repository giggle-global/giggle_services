# milestones/repository.py
from typing import Optional, Dict, Any, List
from pymongo.database import Database
from pymongo import ReturnDocument
from datetime import datetime
import logging
from app.core.db import database

logger = logging.getLogger(__name__)

class MilestoneRepository:
    def __init__(self):
        self.col = database["milestones"]

    def create(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        self.col.insert_one(doc)
        return self.get_by_id(doc["milestone_id"])

    def get_by_id(self, milestone_id: str) -> Optional[Dict[str, Any]]:
        return self.col.find_one({"milestone_id": milestone_id}, {"_id": 0})

    def list_for_agreement(self, agreement_id: str) -> List[Dict[str, Any]]:
        return list(self.col.find({"agreement_id": agreement_id}, {"_id": 0}).sort("created_at", 1))

    def update(self, milestone_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        update_fields["updated_at"] = datetime.utcnow()
        res = self.col.find_one_and_update(
            {"milestone_id": milestone_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        return res

    def delete(self, milestone_id: str) -> bool:
        res = self.col.delete_one({"milestone_id": milestone_id})
        return res.deleted_count > 0
