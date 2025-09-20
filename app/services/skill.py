# app/services/skill.py
from typing import List, Optional
from app.repositories.skill import SkillRepository
from app.models.skill import SkillCreate, SkillLevel, UserSkillEntry
from fastapi import HTTPException

class SkillService:
    def __init__(self, repo: SkillRepository = None):
        self.repo = repo or SkillRepository()

    def seed_skills_if_missing(self, names: List[dict]) -> None:
        """names: list of dicts like {'name': 'Python', 'category': 'backend'}"""
        skills = [SkillCreate(**n) for n in names]
        self.repo.seed_skills(skills)

    def list_skills(self, category: Optional[str] = None) -> List[dict]:
        return self.repo.list_skills(category)

    def validate_user_skill_entries(self, entries: List[UserSkillEntry]) -> List[dict]:
        """Validate that skill_ids exist and level is valid. Return normalized list."""
        if not entries:
            return []

        skill_ids = [e.skill_id for e in entries]
        stored = {s["skill_id"]: s for s in self.repo.get_skills_by_ids(skill_ids)}
        result = []
        for e in entries:
            if e.skill_id not in stored:
                raise HTTPException(400, f"Skill not found: {e.skill_id}")
            if e.level not in SkillLevel:
                raise HTTPException(400, f"Invalid level for skill {e.skill_id}: {e.level}")
            result.append({"skill_id": e.skill_id, "level": e.level.value, "skill_name": stored[e.skill_id]["name"]})
        return result
