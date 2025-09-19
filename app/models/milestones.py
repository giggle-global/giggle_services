# milestones/models.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from uuid import uuid4

def gen_id() -> str:
    return uuid4().hex

class MilestoneStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"

class Deliverable(BaseModel):
    id: str = Field(default_factory=gen_id)
    title: str
    description: Optional[str] = None
    file_urls: List[str] = Field(default_factory=list)

class PaymentBreakdown(BaseModel):
    amount: float = Field(..., ge=0)
    percent: Optional[float] = Field(None, ge=0, le=100)
    currency: str = "INR"
    payment_released: bool = False
    payout_reference: Optional[str] = None

class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    est_start_date: Optional[date] = None
    payment: PaymentBreakdown
    deliverables: Optional[List[Deliverable]] = None

class MilestoneUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    due_date: Optional[date]
    est_start_date: Optional[date]
    start_date: Optional[date]
    completed_date: Optional[date]
    payment: Optional[PaymentBreakdown]
    deliverables: Optional[List[Deliverable]]
    progress: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[MilestoneStatus]
    approver_comments: Optional[str] = None

class MilestoneInDB(BaseModel):
    milestone_id: str = Field(default_factory=gen_id)
    agreement_id: str
    title: str
    description: Optional[str] = None

    due_date: Optional[date] = None
    est_start_date: Optional[date] = None
    start_date: Optional[date] = None
    completed_date: Optional[date] = None

    payment: PaymentBreakdown
    deliverables: List[Deliverable] = Field(default_factory=list)

    progress: int = Field(0, ge=0, le=100)
    status: MilestoneStatus = MilestoneStatus.PENDING

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
