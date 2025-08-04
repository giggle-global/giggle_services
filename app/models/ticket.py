from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from enum import Enum
import datetime

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"

class TimelineAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    ADMIN_COMMENT = "admin_comment"
    FREELANCER_COMMENT = "freelancer_comment"
    STATUS_CHANGED = "status_changed"
    REOPENED = "reopened"
    CLOSED = "closed"

class TimelineEntry(BaseModel):
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    action: TimelineAction
    user_id: str
    user_role: str
    comment: Optional[str] = None
    status: Optional[TicketStatus] = None

class TicketCreate(BaseModel):
    client_id: str
    subject: str
    description: str

class TicketUpdate(BaseModel):
    subject: Optional[str]
    description: Optional[str]

class TicketStatusUpdate(BaseModel):
    status: TicketStatus

class TicketAdminResponse(BaseModel):
    comment: str

class TicketOut(BaseModel):
    ticket_id: str
    freelancer_id: str
    client_id: str
    subject: str
    description: str
    status: TicketStatus
    solution: Optional[str] = None
    timeline: Optional[List[TimelineEntry]] = None
