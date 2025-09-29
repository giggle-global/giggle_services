# app/models/review.py
from pydantic import BaseModel, Field, conint
from typing import Optional
from enum import Enum

class RoleEnum(str, Enum):
    CLIENT = "CL"
    FREELANCER = "FL"
    SUPER_ADMIN = "SA"

class ReviewBase(BaseModel):
    client_id: str
    freelancer_id: str
    stars: conint(ge=1, le=5)  # integer 1..5
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    # created_at will be set by repository/service as epoch int
    pass

class ReviewUpdate(BaseModel):
    stars: Optional[conint(ge=1, le=5)] = None
    comment: Optional[str] = None

class ReviewOut(ReviewBase):
    review_id: str
    created_at: int
    updated_at: Optional[int] = None

    # extra fields from lookup
    client_first_name: Optional[str] = None
    client_last_name: Optional[str] = None
    freelancer_first_name: Optional[str] = None
    freelancer_last_name: Optional[str] = None

    class Config:
        from_attributes = True
    
