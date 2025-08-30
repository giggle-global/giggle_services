from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Message(BaseModel):
    id: Optional[str] = Field(alias="_id", example="64f7b8d9e138f9b2d7a12345")
    project_id: str = Field(..., example="prj-1001")
    chat_id: str = Field(..., example="chat-2001")
    sender_id: str = Field(..., example="user-001")
    sender_role: str = Field(..., example="CL")  # CL = Client, FL = Freelancer, SA = Super Admin
    message: str = Field(..., example="Hello, I need an update on the project status.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, example="2025-08-30T12:45:32.000Z")
    seen_by: List[str] = Field(default_factory=list, example=["user-002"])

    class Config:
        schema_extra = {
            "example": {
                "_id": "64f7b8d9e138f9b2d7a12345",
                "project_id": "prj-1001",
                "chat_id": "chat-2001",
                "sender_id": "user-001",
                "sender_role": "CL",
                "message": "Hello, I need an update on the project status.",
                "timestamp": "2025-08-30T12:45:32.000Z",
                "seen_by": ["user-002"]
            }
        }


class ChatSession(BaseModel):
    id: Optional[str] = Field(alias="_id", example="chat-2001")
    project_id: str = Field(..., example="prj-1001")
    client_id: str = Field(..., example="user-001")
    freelancer_id: str = Field(..., example="user-002")
    created_at: datetime = Field(default_factory=datetime.utcnow, example="2025-08-29T10:15:20.000Z")
    last_updated: datetime = Field(default_factory=datetime.utcnow, example="2025-08-30T12:45:32.000Z")

    class Config:
        schema_extra = {
            "example": {
                "_id": "chat-2001",
                "project_id": "prj-1001",
                "client_id": "user-001",
                "freelancer_id": "user-002",
                "created_at": "2025-08-29T10:15:20.000Z",
                "last_updated": "2025-08-30T12:45:32.000Z"
            }
        }


class MessageIn(BaseModel):
    message: str = Field(..., example="Can you send me the wireframes by tomorrow?")

    class Config:
        schema_extra = {
            "example": {
                "message": "Can you send me the wireframes by tomorrow?"
            }
        }


class MessageOut(BaseModel):
    id: str = Field(..., example="64f7b8d9e138f9b2d7a12346")
    project_id: str = Field(..., example="prj-1001")
    sender_id: str = Field(..., example="user-002")
    sender_role: str = Field(..., example="FL")
    message: str = Field(..., example="Sure, I’ll share them in the morning.")
    timestamp: datetime = Field(..., example="2025-08-30T14:20:15.000Z")
    seen_by: List[str] = Field(..., example=["user-001"])

    class Config:
        schema_extra = {
            "example": {
                "id": "64f7b8d9e138f9b2d7a12346",
                "project_id": "prj-1001",
                "sender_id": "user-002",
                "sender_role": "FL",
                "message": "Sure, I’ll share them in the morning.",
                "timestamp": "2025-08-30T14:20:15.000Z",
                "seen_by": ["user-001"]
            }
        }


class ChatSessionOut(BaseModel):
    id: str = Field(..., example="chat-2001")
    project_id: str = Field(..., example="prj-1001")
    client_id: str = Field(..., example="user-001")
    freelancer_id: str = Field(..., example="user-002")
    created_at: datetime = Field(..., example="2025-08-29T10:15:20.000Z")
    last_updated: datetime = Field(..., example="2025-08-30T14:20:15.000Z")

    class Config:
        schema_extra = {
            "example": {
                "id": "chat-2001",
                "project_id": "prj-1001",
                "client_id": "user-001",
                "freelancer_id": "user-002",
                "created_at": "2025-08-29T10:15:20.000Z",
                "last_updated": "2025-08-30T14:20:15.000Z"
            }
        }
