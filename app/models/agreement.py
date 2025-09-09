# app/models/agreement.py
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class AgreementStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REOPENED = "REOPENED"

class TimelineAction(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    COMMENT = "COMMENT"

class Milestone(BaseModel):
    title: str
    due_date_epoch: Optional[int] = None  # epoch seconds
    amount: float = 0.0
    description: Optional[str] = None

class TimelineEntry(BaseModel):
    timestamp: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    action: TimelineAction
    user_id: str
    user_role: str
    note: Optional[str] = None

class AgreementCreate(BaseModel):
    project_title: str
    client_id: str
    freelancer_id: str
    project_scope: Optional[str] = None
    milestones: Optional[List[Milestone]] = []
    start_date_epoch: Optional[int] = None
    end_date_epoch: Optional[int] = None
    rate: Optional[float] = None  # per hour or per agreed unit
    duration_weeks: Optional[int] = None
    additional_terms: Optional[str] = None
    # digital signature fields will be provided when client accepts
    # not required during creation

class AgreementUpdate(BaseModel):
    project_title: Optional[str] = None
    project_scope: Optional[str] = None
    milestones: Optional[List[Milestone]] = None
    start_date_epoch: Optional[int] = None
    end_date_epoch: Optional[int] = None
    rate: Optional[float] = None
    duration_weeks: Optional[int] = None
    additional_terms: Optional[str] = None

class AgreementSign(BaseModel):
    signer_name: str
    signer_date_epoch: int
    digital_signature_field: Optional[str] = None  # base64 or identifier

class AgreementOut(BaseModel):
    agreement_id: str
    project_title: str
    client_id: str
    freelancer_id: str
    project_scope: Optional[str]
    milestones: List[Milestone]
    start_date_epoch: Optional[int]
    end_date_epoch: Optional[int]
    rate: Optional[float]
    duration_weeks: Optional[int]
    additional_terms: Optional[str]
    total_amount: float
    status: AgreementStatus
    created_at: int
    updated_at: Optional[int]
    timeline: List[TimelineEntry]
    client_signature: Optional[Dict] = None  # {signer_name, signer_date_epoch, digital_signature_field}
    freelancer_signature: Optional[Dict] = None  # optional if you want freelancer to sign
