# agreements/repository.py
from typing import List, Optional, Dict, Any
from pymongo.database import Database
from pymongo import ReturnDocument
from datetime import datetime
import logging
from app.core.db import database

logger = logging.getLogger(__name__)

class AgreementRepository:
    def __init__(self):
        self.col = database["agreements"]

    def create(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        self.col.insert_one(doc)
        return self.get_by_id(doc["agreement_id"])

    def get_by_id(self, agreement_id: str) -> Optional[Dict[str, Any]]:
        return self.col.find_one({"agreement_id": agreement_id}, {"_id": 0})
    
    def get_filtered(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        return list(self.col.find(filter, {"_id": 0}))

    def update(self, agreement_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        update_fields["updated_at"] = datetime.utcnow()
        res = self.col.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        return res

    def add_milestone(self, agreement_id: str, milestone_id: str) -> Optional[Dict[str, Any]]:
        print("Adding milestone to agreement:", agreement_id, milestone_id)
        res = self.col.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$push": {"milestones": milestone_id}, "$set": {"updated_at": datetime.utcnow()}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        print("Updated agreement with new milestone:", res)
        return res

    def set_status(self, agreement_id: str, status: str) -> Optional[Dict[str, Any]]:
        return self.update(agreement_id, {"status": status})
