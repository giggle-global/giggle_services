from typing import Optional, List
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
    timestamp: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow,
        example="2025-08-30T12:45:32.000Z"
    )
    action: TimelineAction = Field(..., example="status_changed")
    user_id: str = Field(..., example="user-001")
    user_role: str = Field(..., example="CL")  # CL, FL, or Admin
    comment: Optional[str] = Field(None, example="Ticket moved to in-progress")
    status: Optional[TicketStatus] = Field(None, example="in_progress")

    class Config:
        schema_extra = {
            "example": {
                "timestamp": "2025-08-30T12:45:32.000Z",
                "action": "status_changed",
                "user_id": "user-001",
                "user_role": "CL",
                "comment": "Ticket moved to in-progress",
                "status": "in_progress"
            }
        }

class TicketCreate(BaseModel):
    client_id: str = Field(..., example="user-001")
    subject: str = Field(..., example="Unable to access project dashboard")
    description: str = Field(..., example="When I log in, the dashboard page shows a 500 error.")

    class Config:
        schema_extra = {
            "example": {
                "client_id": "user-001",
                "subject": "Unable to access project dashboard",
                "description": "When I log in, the dashboard page shows a 500 error."
            }
        }

class TicketUpdate(BaseModel):
    subject: Optional[str] = Field(None, example="Error when accessing dashboard")
    description: Optional[str] = Field(None, example="Getting a 500 Internal Server Error")

    class Config:
        schema_extra = {
            "example": {
                "subject": "Error when accessing dashboard",
                "description": "Getting a 500 Internal Server Error"
            }
        }

class TicketStatusUpdate(BaseModel):
    status: TicketStatus = Field(..., example="resolved")

    class Config:
        schema_extra = {
            "example": {
                "status": "resolved"
            }
        }

class TicketAdminResponse(BaseModel):
    comment: str = Field(..., example="Please clear your cache and try again.")

    class Config:
        schema_extra = {
            "example": {
                "comment": "Please clear your cache and try again."
            }
        }

class TicketOut(BaseModel):
    ticket_id: str = Field(..., example="tick-12345")
    freelancer_id: str = Field(..., example="user-002")
    client_id: str = Field(..., example="user-001")
    subject: str = Field(..., example="Unable to access project dashboard")
    description: str = Field(..., example="When I log in, the dashboard page shows a 500 error.")
    status: TicketStatus = Field(..., example="open")
    solution: Optional[str] = Field(None, example="Issue resolved by updating API gateway.")
    timeline: Optional[List[TimelineEntry]] = Field(
        None,
        example=[
            {
                "timestamp": "2025-08-30T12:45:32.000Z",
                "action": "created",
                "user_id": "user-001",
                "user_role": "CL",
                "comment": "Ticket created",
                "status": "open"
            },
            {
                "timestamp": "2025-08-30T14:10:15.000Z",
                "action": "admin_comment",
                "user_id": "admin-001",
                "user_role": "Admin",
                "comment": "We are checking the server logs",
                "status": "in_progress"
            }
        ]
    )

    class Config:
        schema_extra = {
            "example": {
                "ticket_id": "tick-12345",
                "freelancer_id": "user-002",
                "client_id": "user-001",
                "subject": "Unable to access project dashboard",
                "description": "When I log in, the dashboard page shows a 500 error.",
                "status": "open",
                "solution": None,
                "timeline": [
                    {
                        "timestamp": "2025-08-30T12:45:32.000Z",
                        "action": "created",
                        "user_id": "user-001",
                        "user_role": "CL",
                        "comment": "Ticket created",
                        "status": "open"
                    },
                    {
                        "timestamp": "2025-08-30T14:10:15.000Z",
                        "action": "admin_comment",
                        "user_id": "admin-001",
                        "user_role": "Admin",
                        "comment": "We are checking the server logs",
                        "status": "in_progress"
                    }
                ]
            }
        }
