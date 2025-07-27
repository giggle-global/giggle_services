from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class Message(BaseModel):
    id: Optional[str] = Field(alias="_id")
    chat_id: str
    sender_id: str
    sender_role: str  # CL, FL, SA
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    seen_by: List[str] = []

class ChatSession(BaseModel):
    id: Optional[str] = Field(alias="_id")
    client_id: str
    freelancer_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)




class MessageIn(BaseModel):
    message: str

class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_role: str
    message: str
    timestamp: datetime
    seen_by: List[str]

class ChatSessionOut(BaseModel):
    id: str
    client_id: str
    freelancer_id: str
    created_at: datetime
    last_updated: datetime

