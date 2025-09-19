# agreements/models.py
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime, date
from uuid import uuid4

def gen_id() -> str:
    return uuid4().hex

class AgreementStatus(str, Enum):
    DRAFT = "Draft"
    PENDING_SIGNATURE = "PendingSignature"
    ACTIVE = "Active"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"

class SignatureType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DRAW = "draw"
    DIGITAL = "digital"

class UserRef(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None

class SignatureRecord(BaseModel):
    user_id: str
    name: Optional[str] = None
    signed_at: datetime = Field(default_factory=datetime.utcnow)
    signature_type: SignatureType = SignatureType.TEXT
    signature_value: Optional[str] = None

class PaymentSummary(BaseModel):
    total_amount: float = 0.0
    currency: str = "INR"

# Create / Update / InDB
class AgreementCreate(BaseModel):
    title: str
    description: Optional[str] = None
    client: UserRef
    freelancer: UserRef

    # Rate fields (UI shows Rate + Start/End)
    rate: float = Field(..., ge=0, example=1200)
    rate_unit: Optional[str] = Field("day", example="day")  # day, week, hour
    currency: Optional[str] = Field("INR")

    start_date: date
    end_date: date

    project_scope: Optional[str] = None
    additional_terms: Optional[str] = None

    # Optional initial milestone definitions (list of dicts matching milestone create)
    milestones: Optional[List[dict]] = None

class AgreementUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    rate: Optional[float]
    rate_unit: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    project_scope: Optional[str]
    additional_terms: Optional[str]
    # Do not allow client/freelancer to be changed via normal update

class AgreementInDB(BaseModel):
    agreement_id: str = Field(default_factory=gen_id)
    title: str
    description: Optional[str] = None
    client: UserRef
    freelancer: UserRef

    rate: float
    rate_unit: str = "day"
    currency: str = "INR"

    start_date: date
    end_date: date

    project_scope: Optional[str] = None
    additional_terms: Optional[str] = None

    status: AgreementStatus = AgreementStatus.DRAFT
    client_signed: bool = False
    freelancer_signed: bool = False
    signatures: Dict[str, SignatureRecord] = Field(default_factory=dict)

    # milestone ids
    milestones: List[str] = Field(default_factory=list)

    # summary
    total_amount: float = 0.0
    num_milestones: int = 0
    duration_days: Optional[int] = None

    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_reason: Optional[str] = None
    exported_pdf_url: Optional[str] = None
    draft: bool = True

    class Config:
        orm_mode = True
