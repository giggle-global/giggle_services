from typing import Optional
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
        schema_extra = {
            "example": {
                "project_id": "prj-1001",
                "freelancer_id": "user-002"
            }
        }


class RequestUpdate(BaseModel):
    status: RequestStatus = Field(..., example=RequestStatus.ACCEPTED.value)

    class Config:
        schema_extra = {
            "example": {
                "status": "accepted"
            }
        }


class RequestOut(BaseModel):
    request_id: str = Field(..., example="req-12345")
    client_id: str = Field(..., example="user-001")
    freelancer_id: str = Field(..., example="user-002")
    status: RequestStatus = Field(..., example=RequestStatus.PENDING.value)

    class Config:
        schema_extra = {
            "example": {
                "request_id": "req-12345",
                "client_id": "user-001",
                "freelancer_id": "user-002",
                "status": "pending"
            }
        }
