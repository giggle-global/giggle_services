# app/models/token.py
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum

class TokenTargetRole(str, Enum):
    FREELANCER = "FL"

class SignupTokenBase(BaseModel):
    token: str
    generated_by: str
    target_role: TokenTargetRole = TokenTargetRole.FREELANCER
    created_at: datetime
    expires_at: datetime
    used: bool = False
    used_by: Optional[str] = None
    used_at: Optional[datetime] = None

class SignupTokenCreate(BaseModel):
    generated_by: str
    target_role: TokenTargetRole = TokenTargetRole.FREELANCER
    ttl_seconds: int = 24 * 3600  # default 24 hours

class SignupTokenOut(BaseModel):
    token: str
    generated_by: str
    target_role: TokenTargetRole
    created_at: datetime
    expires_at: datetime
    used: bool
    used_by: Optional[str]
    used_at: Optional[datetime]
