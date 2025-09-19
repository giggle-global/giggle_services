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

    class Config:
        json_schema_extra = {
            "example": {
                "id": "deliv001",
                "title": "Wireframes",
                "description": "Initial wireframes",
                "file_urls": ["https://example.com/wireframes.pdf"]
            }
        }

class PaymentBreakdown(BaseModel):
    amount: float = Field(..., ge=0)
    percent: Optional[float] = Field(None, ge=0, le=100)
    currency: str = "INR"
    payment_released: bool = False
    payout_reference: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 10000,
                "percent": 25,
                "currency": "INR",
                "payment_released": False
            }
        }

class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[int] = None
    est_start_date: Optional[int] = None
    payment: PaymentBreakdown
    deliverables: Optional[List[Deliverable]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Research & Planning",
                "description": "Gather requirements and wireframes",
                "due_date": "2025-09-30",
                "est_start_date": "2025-09-25",
                "payment": {"amount": 10000, "percent": 25, "currency": "INR"},
                "deliverables": [{"title": "Wireframes", "file_urls": ["https://example.com/wireframe.pdf"]}]
            }
        }

class MilestoneUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    due_date: Optional[int]
    est_start_date: Optional[int]
    start_date: Optional[int]
    completed_date: Optional[int]
    payment: Optional[PaymentBreakdown]
    deliverables: Optional[List[Deliverable]]
    progress: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[MilestoneStatus]
    approver_comments: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "progress": 65,
                "status": "InProgress"
            }
        }

class MilestoneInDB(BaseModel):
    milestone_id: str = Field(default_factory=gen_id)
    agreement_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[int] = None
    est_start_date: Optional[int] = None    # epoch
    start_date: Optional[int] = None        # epoch
    completed_date: Optional[int] = None    # epoch
    payment: PaymentBreakdown
    deliverables: List[Deliverable] = Field(default_factory=list)
    progress: int = Field(0, ge=0, le=100)
    status: MilestoneStatus = MilestoneStatus.PENDING
    created_at: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    updated_at: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    approved_by: Optional[str] = None
    approved_at: Optional[int] = None
    approval_notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "milestone_id": "milestone123",
                "agreement_id": "7f3d89f47c1a4b21a2f0c0a8e9d4f7bb",
                "title": "Research & Planning",
                "description": "Gather requirements and wireframes",
                "due_date": "2025-09-30",
                "est_start_date": "2025-09-25",
                "payment": {"amount": 10000, "percent": 25, "currency": "INR"},
                "progress": 0,
                "status": "Pending",
                "created_at": "2025-09-19T14:30:00.000Z",
                "updated_at": "2025-09-19T14:30:00.000Z"
            }
        }
