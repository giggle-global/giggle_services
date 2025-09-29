# app/repositories/portfolio.py
import logging
from typing import Dict, Any, List, Optional
from pymongo.errors import PyMongoError
from bson import ObjectId
from datetime import datetime

from app.core.db import database  # adjust this import to your project's DB accessor

logger = logging.getLogger(__name__)
COLLECTION_NAME = "portfolio_projects"

class PortfolioRepository:
    def __init__(self, db=None):
        # get_db should return a pymongo.database.Database instance
        self.col = database["portfolio"]

    def _to_out(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return None
        # normalize mongo doc to API-friendly dict
        out = {
            "id": str(doc.get("_id") or doc.get("id")),
            "user_id": doc.get("user_id"),
            "title": doc.get("title"),
            "description": doc.get("description"),
            "technologies": doc.get("technologies") or [],
            "github_link": doc.get("github_link"),
            "portfolio_link": doc.get("portfolio_link"),
            "cover_image": doc.get("cover_image"),
            "status": doc.get("status"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }
        return out

    def create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload.copy()
        payload.setdefault("status", "active")
        payload.setdefault("created_at", datetime.utcnow())
        payload.setdefault("updated_at", datetime.utcnow())
        try:
            result = self.col.insert_one(payload)
            doc = self.col.find_one({"_id": result.inserted_id})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error creating portfolio project: %s", payload.get("title"))
            raise

    def find_by_user(self, user_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        try:
            cursor = self.col.find({"user_id": user_id, "status": {"$ne": "deleted"}}).sort("created_at", -1).skip(skip).limit(limit)
            return [self._to_out(doc) for doc in cursor]
        except PyMongoError:
            logger.exception("Mongo error listing projects for user: %s", user_id)
            raise

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id
            doc = self.col.find_one({"_id": oid})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error fetching project id=%s", project_id)
            raise

    def update_project(self, project_id: str, update_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            oid = ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id
            update_payload["updated_at"] = datetime.utcnow()
            result = self.col.find_one_and_update({"_id": oid}, {"$set": update_payload}, return_document=True)
            return self._to_out(result)
        except PyMongoError:
            logger.exception("Mongo error updating project id=%s", project_id)
            raise

    def soft_delete(self, project_id: str, performed_by: str) -> Optional[Dict[str, Any]]:
        try:
            oid = ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id
            update = {
                "status": "deleted",
                "updated_at": datetime.utcnow(),
                "deleted_by": performed_by
            }
            result = self.col.find_one_and_update({"_id": oid}, {"$set": update}, return_document=True)
            return self._to_out(result)
        except PyMongoError:
            logger.exception("Mongo error deleting project id=%s", project_id)
            raise
