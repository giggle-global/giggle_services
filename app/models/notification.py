from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class NotificationType(str, Enum):
    REQUEST_RECEIVED = "request_received"
    MILESTONE_REMINDER = "milestone_reminder"
    REQUEST_ACCEPTED = "request_accepted"
    REQUEST_REJECTED = "request_rejected"
    MILESTONE_COMPLETED = "milestone_completed"
    MILESTONE_APPROVED = "milestone_approved"
    AGREEMENT_CREATED = "agreement_created"
    CLIENT_REQUEST_LIMIT_REACHED = "client_request_limit_reached"
    AGREEMENT_SIGN_REMINDER = "agreement_sign_reminder"

class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"

class NotificationCreate(BaseModel):
    user_id: str = Field(..., description="User who will receive the notification")
    type: NotificationType = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data (e.g., request_id, milestone_id)")
    link: Optional[str] = Field(None, description="Link to related page")

class NotificationOut(BaseModel):
    notification_id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    status: NotificationStatus
    data: Optional[Dict[str, Any]] = None
    link: Optional[str] = None
    created_at: int
    read_at: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif-123",
                "user_id": "user-001",
                "type": "request_received",
                "title": "New Request",
                "message": "You have received a new project request",
                "status": "unread",
                "data": {"request_id": "req-123", "project_id": "proj-456"},
                "link": "/freelancer/gig",
                "created_at": 1633036800,
                "read_at": None
            }
        }

