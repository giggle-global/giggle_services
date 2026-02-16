from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4

class RequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RequestCreate(BaseModel):
    project_id: str = Field(..., example="prj-1001")   # ID of project
    freelancer_id: str = Field(..., example="user-002")  # user_id of freelancer

    class Config:
       json_schema_extra= {
            "example": {
                "project_id": "prj-1001",
                "freelancer_id": "user-002"
            }
        }

class CancelRequestByParties(BaseModel):
    project_id: str = Field(..., example="proj123")
    freelancer_id: str = Field(..., example="free123")
    client_id: str = Field(..., example="client123")

    class Config:
       json_schema_extra= {
            "example": {
                "project_id": "proj123",
                "freelancer_id": "free123",
                "client_id": "client123"
            }
        }


class RequestUpdate(BaseModel):
    status: RequestStatus = Field(..., example=RequestStatus.ACCEPTED.value)

    class Config:
       json_schema_extra= {
            "example": {
                "status": "accepted"
            }
        }


class RequestOut(BaseModel):
    request_id: str = Field(..., example="req-12345")
    project_id: str = Field(..., example="prj-1001")
    client_id: str = Field(..., example="user-001")
    freelancer_id: str = Field(..., example="user-002")
    client_name: str = Field(..., example="John Doe")
    freelancer_name: str = Field(..., example="Jane Smith")
    status: RequestStatus = Field(..., example=RequestStatus.PENDING.value)
    created_at: Optional[int] = Field(None, example=1633036800)  # epoch seconds
    project_title: Optional[str] = Field(None, example="Website Development")
    client_profile_pic: Optional[str] = Field(None, example="http://example.com/profiles/user-001.jpg")
    freelancer_profile_pic: Optional[str] = Field(None, example="http://example.com/profiles/user-002.jpg")
    has_dispute: Optional[bool] = Field(False, example=False)
    dispute_timestamp: Optional[datetime] = Field(None, example="2024-05-20T10:00:00Z")
    ticket_id: Optional[str] = Field(None, example="tick-12345")

    class Config:
       json_schema_extra= {
            "example": {
                "request_id": "req-12345",
                "client_id": "user-001",
                "freelancer_id": "user-002",
                "client_name": "John Doe",
                "freelancer_name": "Jane Smith",
                "status": "pending"
            }
        }
