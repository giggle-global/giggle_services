"""
Meeting models for Google Meet integration
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class MeetingStatus(str, Enum):
    """Meeting status"""
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MeetingCreate(BaseModel):
    """Model for creating a meeting"""
    agreement_id: Optional[str] = Field(None, description="Agreement ID this meeting is associated with (optional for messages page)")
    client_id: Optional[str] = Field(None, description="Client ID (required if agreement_id is not provided)")
    freelancer_id: Optional[str] = Field(None, description="Freelancer ID (required if agreement_id is not provided)")
    title: str = Field(..., description="Meeting title")
    description: Optional[str] = Field(None, description="Meeting description")
    scheduled_time: int = Field(..., description="Scheduled time as Unix timestamp (UTC)")
    duration_minutes: int = Field(30, ge=15, le=480, description="Meeting duration in minutes (15-480)")
    timezone: str = Field("UTC", description="Timezone for the meeting")


class MeetingUpdate(BaseModel):
    """Model for updating a meeting"""
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[int] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    status: Optional[MeetingStatus] = None
    google_meet_link: Optional[str] = None


class MeetingLinkUpdate(BaseModel):
    """Model for updating meeting link only"""
    google_meet_link: str = Field(..., description="Google Meet link URL")


class MeetingOut(BaseModel):
    """Model for meeting output"""
    meeting_id: str
    agreement_id: Optional[str] = None  # Optional - not required for messages page meetings
    title: str
    description: Optional[str] = None
    scheduled_time: int
    duration_minutes: int
    timezone: str
    status: MeetingStatus
    google_meet_link: Optional[str] = None
    google_calendar_event_id: Optional[str] = None
    client: Dict[str, Any] = Field(..., description="Client user reference")
    freelancer: Dict[str, Any] = Field(..., description="Freelancer user reference")
    created_by: str
    created_at: int
    updated_at: int
    cancelled_at: Optional[int] = None
    cancelled_by: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "meeting_id": "meet-123",
                "agreement_id": "agr-456",
                "title": "Project Kickoff Meeting",
                "description": "Discuss project requirements and timeline",
                "scheduled_time": 1704067200,
                "duration_minutes": 60,
                "timezone": "UTC",
                "status": "scheduled",
                "google_meet_link": "https://meet.google.com/abc-defg-hij",
                "google_calendar_event_id": "event123@google.com",
                "client": {
                    "user_id": "client-123",
                    "name": "John Doe",
                    "email": "john@example.com"
                },
                "freelancer": {
                    "user_id": "freelancer-456",
                    "name": "Jane Smith",
                    "email": "jane@example.com"
                },
                "created_by": "client-123",
                "created_at": 1704060000,
                "updated_at": 1704060000,
                "cancelled_at": None,
                "cancelled_by": None
            }
        }


class MeetingFilter(BaseModel):
    """Model for filtering meetings"""
    agreement_id: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[MeetingStatus] = None
    upcoming_only: Optional[bool] = False


