# app/models/skill.py
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime
from uuid import uuid4

class SkillLevel(str, Enum):
    BASIC = "basic"
    EXPERT = "expert"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class SkillBase(BaseModel):
    skill_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    category: Optional[str] = "general"
    industry: Optional[str] = "general"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SkillCreate(BaseModel):
    name: str
    category: Optional[str] = "general"
    industry: Optional[str] = "general"

class SkillOut(SkillBase):
    pass

class UserSkillEntry(BaseModel):
    skill_id: str
    skill_name: Optional[str] = None
    level: SkillLevel
