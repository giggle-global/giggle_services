# app/repositories/skill.py
from pymongo.collection import Collection
from app.core.db import database
from typing import List, Optional
from app.models.skill import SkillCreate
from datetime import datetime
from uuid import uuid4
from pymongo.errors import PyMongoError

class SkillRepository:
    def __init__(self):
        self.collection: Collection = database["skills"]
        # create unique index on name to avoid duplicates
        try:
            self.collection.create_index("name", unique=True)
        except Exception:
            pass

    def seed_skills(self, skills: List[SkillCreate]) -> None:
        """Insert skills that do not already exist (idempotent)."""
        for s in skills:
            try:
                now = datetime.utcnow()
                update_fields = {
                    "category": s.category or "general",
                    "industry": s.industry or "general",
                    "updated_at": now,
                }

                insert_fields = {
                    "skill_id": str(uuid4()),
                    "name": s.name,
                    "created_at": now,
                }

                self.collection.update_one(
                    {"name": s.name},
                    {
                        "$set": update_fields,          # always update these
                        "$setOnInsert": insert_fields,  # only on first insert
                    },
                    upsert=True,
                )

            except PyMongoError as e:
                # log or handle in real app
                continue

    def list_skills(self, category: Optional[str] = None) -> List[dict]:
        q = {}
        if category:
            q["category"] = category
        return list(self.collection.find(q, {"_id": 0}).sort("name", 1))

    def get_skill_by_id(self, skill_id: str) -> Optional[dict]:
        return self.collection.find_one({"skill_id": skill_id}, {"_id": 0})

    def get_skills_by_ids(self, skill_ids: List[str]) -> List[dict]:
        return list(self.collection.find({"skill_id": {"$in": skill_ids}}, {"_id": 0}))
