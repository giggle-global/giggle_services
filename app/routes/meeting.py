"""
Meeting routes for Google Meet integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from typing import Dict, Any, List, Optional
from app.models.meeting import MeetingCreate, MeetingUpdate, MeetingOut, MeetingFilter
from app.services.meeting import MeetingService
from app.core.keycloak import get_current_user
from app.schemas.response import ok, APIResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def get_meeting_service() -> MeetingService:
    return MeetingService()


@router.post("/", response_model=APIResponse[MeetingOut], status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Create a new meeting with Google Meet link"""
    try:
        meeting = svc.create_meeting(payload, current_user["user_id"])
        return ok(meeting, "Meeting created successfully", status.HTTP_201_CREATED)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating meeting: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create meeting")


@router.get("/{meeting_id}", response_model=APIResponse[MeetingOut])
def get_meeting(
    meeting_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Get a meeting by ID"""
    try:
        meeting = svc.get_meeting(meeting_id)
        # Verify user has access
        user_id = current_user["user_id"]
        if user_id not in [
            meeting.get("client", {}).get("user_id"),
            meeting.get("freelancer", {}).get("user_id")
        ]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this meeting")
        return ok(meeting, "Meeting fetched successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching meeting: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch meeting")


@router.get("/agreement/{agreement_id}", response_model=APIResponse[List[MeetingOut]])
def get_meetings_by_agreement(
    agreement_id: str,
    upcoming_only: bool = Query(False, description="Return only upcoming meetings"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Get all meetings for an agreement"""
    try:
        meetings = svc.get_meetings_by_agreement(agreement_id, upcoming_only)
        return ok(meetings, f"Found {len(meetings)} meetings")
    except Exception as e:
        logger.exception("Error fetching meetings: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch meetings")


@router.get("/user/me", response_model=APIResponse[List[MeetingOut]])
def get_my_meetings(
    upcoming_only: bool = Query(False, description="Return only upcoming meetings"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Get all meetings for the current user"""
    try:
        meetings = svc.get_meetings_by_user(current_user["user_id"], upcoming_only)
        return ok(meetings, f"Found {len(meetings)} meetings")
    except Exception as e:
        logger.exception("Error fetching meetings: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch meetings")


@router.post("/filtered", response_model=APIResponse[List[MeetingOut]])
def get_filtered_meetings(
    filter: MeetingFilter = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Get meetings with filters"""
    try:
        meetings = svc.get_filtered_meetings(filter)
        return ok(meetings, f"Found {len(meetings)} meetings")
    except Exception as e:
        logger.exception("Error fetching filtered meetings: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch meetings")


@router.put("/{meeting_id}", response_model=APIResponse[MeetingOut])
def update_meeting(
    meeting_id: str,
    payload: MeetingUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Update a meeting"""
    try:
        meeting = svc.update_meeting(meeting_id, payload, current_user["user_id"])
        return ok(meeting, "Meeting updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating meeting: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting")


@router.post("/{meeting_id}/cancel", response_model=APIResponse[MeetingOut])
def cancel_meeting(
    meeting_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MeetingService = Depends(get_meeting_service)
):
    """Cancel a meeting"""
    try:
        meeting = svc.cancel_meeting(meeting_id, current_user["user_id"])
        return ok(meeting, "Meeting cancelled successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error cancelling meeting: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel meeting")


