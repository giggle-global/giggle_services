# agreements/models.py
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime, date, time
from uuid import uuid4

from pydantic import field_validator

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

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "client123",
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "avatar_url": "https://example.com/avatars/alice.png"
            }
        }

class SignatureRecord(BaseModel):
    user_id: str
    name: Optional[str] = None
    signed_at: datetime = Field(default_factory=datetime.utcnow)
    signature_type: SignatureType = SignatureType.TEXT
    signature_value: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "client123",
                "name": "Alice Johnson",
                "signed_at": "2025-09-19T14:30:00.000Z",
                "signature_type": "text",
                "signature_value": "Alice J."
            }
        }

class PaymentSummary(BaseModel):
    total_amount: float = 0.0
    currency: str = "INR"

    class Config:
        json_schema_extra = {"example": {"total_amount": 40000, "currency": "INR"}}

# Create / Update / InDB
class AgreementCreate(BaseModel):
    title: str
    description: Optional[str] = None
    client: UserRef
    freelancer: UserRef
    project_id: str

    rate: float = Field(..., ge=0, example=1200)
    rate_unit: Optional[str] = Field("day", example="day")
    currency: Optional[str] = Field("INR")
    start_date: int = Field(..., ge=0, example=1662505600)
    end_date: int = Field(..., ge=0, example=1665097600)

    project_scope: Optional[str] = None
    additional_terms: Optional[str] = None
    milestones: Optional[List[dict]] = None


    class Config:
        json_schema_extra = {
            "example": {
                        "additional_terms": "All IP rights remain with the client",
                        "project_id": "prj-1001",
                        "client": {
                            "email": "alice@example.com",
                            "name": "Alice Johnson",
                            "user_id": "59a9cc4f-a155-4a7e-bad3-d69522bfeef5"
                        },
                        "currency": "INR",
                        "description": "Build an e-commerce website with React, Node.js and payments",
                        "end_date": 1761340800,
                        "freelancer": {
                            "email": "bob@example.com",
                            "name": "Bob Smith",
                            "user_id": "freelancer456"
                        },
                        "milestones": [
                            {
                            "deliverables": [
                                {
                                "file_urls": [
                                    "https://example.com/wireframe.pdf"
                                ],
                                "title": "Wireframes"
                                }
                            ],
                            "description": "Wireframes and requirements",
                            "due_date": 1758758400,
                            "est_start_date": 1758758400,
                            "payment": {
                                "amount": 10000,
                                "currency": "INR",
                                "percent": 25
                            },
                            "title": "Research & Planning"
                            }
                        ],
                        "project_scope": "Frontend, backend, and payment integration",
                        "rate": 1200,
                        "rate_unit": "day",
                        "start_date": 1758758400,
                        "title": "E-commerce Website Development"
                        }
        }

class AgreementUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    rate: Optional[float]
    rate_unit: Optional[str]
    start_date: Optional[int]
    end_date: Optional[int]
    project_scope: Optional[str]
    additional_terms: Optional[str]


    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Agreement Title",
                "rate": 1500,
                "end_date": 1761340800
            }
        }

class AgreementInDB(BaseModel):
    agreement_id: str = Field(default_factory=gen_id)
    title: str
    description: Optional[str] = None
    client: UserRef
    freelancer: UserRef
    rate: float
    rate_unit: str = "day"
    currency: str = "INR"
    start_date: int = Field(..., ge=0, example=1662505600)
    end_date: int = Field(..., ge=0, example=1665097600)
    project_scope: Optional[str] = None
    additional_terms: Optional[str] = None
    status: AgreementStatus = AgreementStatus.DRAFT
    client_signed: bool = False
    freelancer_signed: bool = False
    signatures: Dict[str, SignatureRecord] = Field(default_factory=dict)
    milestones: List[str] = Field(default_factory=list)
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
        json_schema_extra = {
            "example": {
                "agreement_id": "7f3d89f47c1a4b21a2f0c0a8e9d4f7bb",
                "title": "E-commerce Website Development",
                "client": {"user_id": "client123", "name": "Alice Johnson"},
                "freelancer": {"user_id": "freelancer456", "name": "Bob Smith"},
                "rate": 1200,
                "rate_unit": "day",
                "currency": "INR",
                "start_date": 1758758400,
                "end_date": 1761340800,
                "status": "Draft",
                "client_signed": False,
                "freelancer_signed": False,
                "milestones": ["milestone123"],
                "total_amount": 40000,
                "num_milestones": 3,
                "duration_days": 31,
                "created_by": "client123",
                "created_at": "2025-09-19T14:30:00.000Z",
                "updated_at": "2025-09-19T14:30:00.000Z",
                "draft": True
            }
        }


