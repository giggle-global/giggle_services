from typing import Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4

class RequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class RequestCreate(BaseModel):
    client_id: str  # user_id of client (CL)
    freelancer_id: str  # user_id of freelancer (FL)

class RequestUpdate(BaseModel):
    status: RequestStatus

class RequestOut(BaseModel):
    request_id: str
    client_id: str
    freelancer_id: str
    status: RequestStatus
