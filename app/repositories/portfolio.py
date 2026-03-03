# app/repositories/portfolio.py
import logging
import uuid
from typing import Dict, Any, List, Optional
from pymongo.errors import PyMongoError
from datetime import datetime

from fastapi.encoders import jsonable_encoder
from app.core.db import database  # your DB accessor

logger = logging.getLogger(__name__)
COLLECTION_NAME = "portfolio"  # using the same name you had


class PortfolioRepository:
    def __init__(self, db=None):
        self.col = (db or database)[COLLECTION_NAME]

    def _to_out(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        return {
            "id": doc.get("id"),  # custom id (UUID string)
            "user_id": doc.get("user_id"),
            "title": doc.get("title"),
            "description": doc.get("description"),
            "technologies": doc.get("technologies") or [],
            "github_link": doc.get("github_link"),
            "portfolio_link": doc.get("portfolio_link"),
            "cover_image": doc.get("cover_image"),
            "portfolio_pdf": doc.get("portfolio_pdf"),
            "status": doc.get("status"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "source_project_id": doc.get("source_project_id"),  # Include source_project_id to distinguish user-given vs gig-completed portfolios
        }

    def create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload.copy()
        # generate custom UUID id
        payload["id"] = payload.get("id") or uuid.uuid4().hex
        payload.setdefault("status", "active")
        payload.setdefault("created_at", datetime.utcnow())
        payload.setdefault("updated_at", datetime.utcnow())

        # ensure BSON-safe values
        payload = jsonable_encoder(payload)

        try:
            self.col.insert_one(payload)
            doc = self.col.find_one({"id": payload["id"]})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error creating portfolio project: %s", payload.get("title"))
            raise

    def find_by_user(self, user_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        try:
            cursor = (
                self.col.find({"user_id": user_id, "status": {"$ne": "deleted"}})
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            return [self._to_out(doc) for doc in cursor]
        except PyMongoError:
            logger.exception("Mongo error listing projects for user: %s", user_id)
            raise
    
    def find_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Alias for find_by_user (for matching algorithm compatibility)"""
        return self.find_by_user(user_id)

    def find_one_by_user_and_source_project(
        self,
        user_id: str,
        source_project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single portfolio entry for a given user that was auto-created
        from a specific project (source_project_id). Used for idempotent
        upsert when agreements are completed.
        """
        try:
            doc = self.col.find_one(
                {
                    "user_id": user_id,
                    "source_project_id": source_project_id,
                    "status": {"$ne": "deleted"},
                }
            )
            return self._to_out(doc)
        except PyMongoError:
            logger.exception(
                "Mongo error fetching portfolio by user_id=%s and source_project_id=%s",
                user_id,
                source_project_id,
            )
            raise

    def upsert_auto_project_from_source(
        self,
        user_id: str,
        source_project_id: str,
        base_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Idempotently create or update a portfolio project for a freelancer
        based on a source project (from the main projects collection).

        - Ensures at most one active portfolio entry per (user_id, source_project_id)
        - Updates core fields (title, description, technologies, links)
        """
        try:
            existing = self.col.find_one(
                {
                    "user_id": user_id,
                    "source_project_id": source_project_id,
                    "status": {"$ne": "deleted"},
                }
            )

            now = datetime.utcnow()
            if existing:
                update_fields = {
                    "title": base_payload.get("title", existing.get("title")),
                    "description": base_payload.get(
                        "description", existing.get("description")
                    ),
                    "technologies": base_payload.get(
                        "technologies", existing.get("technologies")
                    ),
                    "github_link": base_payload.get(
                        "github_link", existing.get("github_link")
                    ),
                    "portfolio_link": base_payload.get(
                        "portfolio_link", existing.get("portfolio_link")
                    ),
                    "portfolio_pdf": base_payload.get(
                        "portfolio_pdf", existing.get("portfolio_pdf")
                    ),
                    "updated_at": now,
                }
                update_fields = jsonable_encoder(update_fields)
                self.col.update_one({"id": existing.get("id")}, {"$set": update_fields})
                doc = self.col.find_one({"id": existing.get("id")})
                return self._to_out(doc)

            # Create new entry
            payload = base_payload.copy()
            payload["id"] = uuid.uuid4().hex
            payload["user_id"] = user_id
            payload["source_project_id"] = source_project_id
            payload.setdefault("status", "active")
            payload.setdefault("created_at", now)
            payload.setdefault("updated_at", now)

            payload = jsonable_encoder(payload)
            self.col.insert_one(payload)
            doc = self.col.find_one({"id": payload["id"]})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception(
                "Mongo error upserting auto portfolio project for user_id=%s source_project_id=%s",
                user_id,
                source_project_id,
            )
            raise

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.col.find_one({"id": project_id})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error fetching project id=%s", project_id)
            raise

    def update_project(self, project_id: str, update_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            update_payload = update_payload.copy()
            update_payload["updated_at"] = datetime.utcnow()
            update_payload = jsonable_encoder(update_payload)

            res = self.col.update_one({"id": project_id}, {"$set": update_payload})
            if res.matched_count == 0:
                return None
            doc = self.col.find_one({"id": project_id})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error updating project id=%s", project_id)
            raise

    def soft_delete(self, project_id: str, performed_by: str) -> Optional[Dict[str, Any]]:
        try:
            update = {
                "status": "deleted",
                "updated_at": datetime.utcnow(),
                "deleted_by": performed_by,
            }
            res = self.col.update_one({"id": project_id}, {"$set": update})
            if res.matched_count == 0:
                return None
            doc = self.col.find_one({"id": project_id})
            return self._to_out(doc)
        except PyMongoError:
            logger.exception("Mongo error deleting project id=%s", project_id)
            raise
