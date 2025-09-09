# app/repositories/agreement.py
import uuid
import time
from typing import Optional, List
from pymongo.collection import Collection
from fastapi import HTTPException
from app.core.db import database

class AgreementRepository:
    def __init__(self):
        self.collection: Collection = database["agreements"]
        try:
            self.collection.create_index("agreement_id", unique=True)
            self.collection.create_index("client_id")
            self.collection.create_index("freelancer_id")
            self.collection.create_index("status")
        except Exception:
            pass

    def _now_epoch(self) -> int:
        return int(time.time())

    def create(self, payload: dict) -> dict:
        agreement_id = str(uuid.uuid4())
        now = self._now_epoch()
        payload["agreement_id"] = agreement_id
        payload["created_at"] = now
        payload["updated_at"] = None
        # default fields
        payload.setdefault("status", "DRAFT")
        payload.setdefault("timeline", [])
        payload.setdefault("total_amount", payload.get("total_amount", 0.0))
        try:
            self.collection.insert_one(payload)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to create agreement")
        return self.collection.find_one({"agreement_id": agreement_id}, {"_id": 0})

    def update(self, agreement_id: str, update_data: dict) -> dict:
        update_data["updated_at"] = self._now_epoch()
        res = self.collection.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$set": update_data},
            projection={"_id": 0},
            return_document=True
        )
        if not res:
            raise HTTPException(status_code=404, detail="Agreement not found")
        return res

    def add_timeline(self, agreement_id: str, entry: dict):
        res = self.collection.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$push": {"timeline": entry}, "$set": {"updated_at": self._now_epoch()}},
            projection={"_id": 0},
            return_document=True
        )
        if not res:
            raise HTTPException(status_code=404, detail="Agreement not found")
        return res

    def get(self, agreement_id: str) -> Optional[dict]:
        return self.collection.find_one({"agreement_id": agreement_id}, {"_id": 0})

    def list_by_freelancer(self, freelancer_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
        return list(self.collection.find({"freelancer_id": freelancer_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

    def list_by_client(self, client_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
        return list(self.collection.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

    def change_status(self, agreement_id: str, new_status: str) -> dict:
        res = self.collection.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$set": {"status": new_status, "updated_at": self._now_epoch()}},
            projection={"_id": 0},
            return_document=True
        )
        if not res:
            raise HTTPException(status_code=404, detail="Agreement not found")
        return res
