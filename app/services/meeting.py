"""
Meeting service for business logic
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.repositories.meeting import MeetingRepository
from app.repositories.agreements import AgreementRepository
from app.repositories.user import UserRepository
from app.models.meeting import MeetingCreate, MeetingUpdate, MeetingStatus, MeetingFilter
from app.core.google_calendar import GoogleCalendarService
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class MeetingService:
    """Service for meeting operations"""
    
    def __init__(self):
        self.repo = MeetingRepository()
        self.agreement_repo = AgreementRepository()
        self.user_repo = UserRepository()
        self.google_calendar = GoogleCalendarService()
    
    
    def create_meeting(
        self,
        payload: MeetingCreate,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create a new meeting with Google Meet link
        Supports both agreement-based meetings (gig page) and direct client/freelancer meetings (messages page)
        """
        try:
            client = {}
            freelancer = {}
            agreement_title = "Agreement"
            
            # Handle two cases: with agreement_id (gig page) or with client_id/freelancer_id (messages page)
            if payload.agreement_id:
                # Get agreement to verify participants (for gig page)
                agreement = self.agreement_repo.get_by_id(payload.agreement_id)
                if not agreement:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
                
                client = agreement.get("client", {})
                freelancer = agreement.get("freelancer", {})
                agreement_title = agreement.get("title", "Agreement")
                
                # Verify user is part of the agreement
                if created_by not in [client.get("user_id"), freelancer.get("user_id")]:
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        "You are not authorized to create meetings for this agreement"
                    )
            elif payload.client_id and payload.freelancer_id:
                # Get client and freelancer directly from user repository (for messages page)
                try:
                    client_user = self.user_repo.get_user_by_id(payload.client_id)
                    freelancer_user = self.user_repo.get_user_by_id(payload.freelancer_id)
                    
                    # Format client and freelancer in the same structure as agreement
                    client = {
                        "user_id": client_user.get("user_id"),
                        "email": client_user.get("email"),
                        "first_name": client_user.get("first_name", ""),
                        "last_name": client_user.get("last_name", ""),
                        "name": f"{client_user.get('first_name', '')} {client_user.get('last_name', '')}".strip()
                    }
                    freelancer = {
                        "user_id": freelancer_user.get("user_id"),
                        "email": freelancer_user.get("email"),
                        "first_name": freelancer_user.get("first_name", ""),
                        "last_name": freelancer_user.get("last_name", ""),
                        "name": f"{freelancer_user.get('first_name', '')} {freelancer_user.get('last_name', '')}".strip()
                    }
                    
                    # Verify user is either the client or freelancer
                    if created_by not in [payload.client_id, payload.freelancer_id]:
                        raise HTTPException(
                            status.HTTP_403_FORBIDDEN,
                            "You are not authorized to create meetings for this conversation"
                        )
                except HTTPException as e:
                    if e.status_code == 404:
                        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client or freelancer not found")
                    raise
            else:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Either agreement_id or both client_id and freelancer_id must be provided"
                )
            
            # Validate scheduled time is in the future
            now = int(datetime.utcnow().timestamp())
            if payload.scheduled_time <= now:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Scheduled time must be in the future"
                )
            
            # Create Google Calendar event with Meet link
            start_time = datetime.fromtimestamp(payload.scheduled_time)
            end_time = start_time + timedelta(minutes=payload.duration_minutes)
            
            client_email = client.get("email")
            freelancer_email = freelancer.get("email")
            attendees = []
            
            if client_email:
                attendees.append(client_email)
            if freelancer_email:
                attendees.append(freelancer_email)
            
            google_event = None
            meet_link = None
            calendar_event_id = None
            
            # Try to create Google Calendar event with Google Meet link
            try:
                if self.google_calendar.service:
                    if not attendees:
                        logger.warning("No attendees provided. Creating meeting without Google Calendar event.")
                    else:
                        google_event = self.google_calendar.create_meeting(
                            title=payload.title,
                            description=payload.description or f"Meeting for {agreement_title}",
                            start_time=start_time,
                            end_time=end_time,
                            attendees=attendees,
                            timezone=payload.timezone
                        )
                        
                        if google_event and google_event.get("meet_link"):
                            meet_link = google_event.get("meet_link")
                            calendar_event_id = google_event.get("event_id")
                            logger.info("Google Calendar event created with Meet link: %s", calendar_event_id)
                        else:
                            raise Exception("Google Calendar event was created but no Meet link was returned")
                else:
                    logger.warning("Google Calendar service not initialized. Meeting will be created without Meet link. Please configure Google Calendar API or add link manually.")
            except Exception as e:
                # Log the error but continue with meeting creation (allow manual link addition)
                error_msg = str(e)
                logger.error("Error creating Google Calendar event: %s. Meeting will be created without Meet link. Please add it manually.", error_msg)
                logger.exception("Full exception details:")
                # Don't raise exception - allow meeting creation to continue so user can add link manually
            
            # Create meeting in database
            meeting_data = {
                "agreement_id": payload.agreement_id,  # Can be None for messages page meetings
                "title": payload.title,
                "description": payload.description,
                "scheduled_time": payload.scheduled_time,
                "duration_minutes": payload.duration_minutes,
                "timezone": payload.timezone,
                "status": MeetingStatus.SCHEDULED.value,
                "google_meet_link": meet_link,  # Will be None if Google Calendar failed
                "google_calendar_event_id": calendar_event_id,
                "client": client,
                "freelancer": freelancer,
                "created_by": created_by
            }
            
            meeting = self.repo.create(meeting_data)
            meeting_id = meeting.get("meeting_id")
            
            if payload.agreement_id:
                logger.info("Meeting created: %s for agreement: %s", meeting_id, payload.agreement_id)
            else:
                logger.info("Meeting created: %s for client: %s, freelancer: %s", meeting_id, payload.client_id, payload.freelancer_id)
            
            return meeting
            
        except HTTPException:
            raise
        except PyMongoError as e:
            logger.exception("Database error creating meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create meeting")
        except Exception as e:
            logger.exception("Error creating meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create meeting")
    
    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Get a meeting by ID"""
        meeting = self.repo.get_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")
        return meeting
    
    def get_meetings_by_agreement(
        self,
        agreement_id: str,
        upcoming_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all meetings for an agreement"""
        return self.repo.get_by_agreement(agreement_id, upcoming_only)
    
    def get_meetings_by_user(
        self,
        user_id: str,
        upcoming_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all meetings for a user"""
        return self.repo.get_by_user(user_id, upcoming_only)
    
    def update_meeting(
        self,
        meeting_id: str,
        payload: MeetingUpdate,
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a meeting"""
        try:
            meeting = self.repo.get_by_id(meeting_id)
            if not meeting:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")
            
            # Verify user is part of the agreement
            if updated_by not in [
                meeting.get("client", {}).get("user_id"),
                meeting.get("freelancer", {}).get("user_id")
            ]:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not authorized to update this meeting"
                )
            
            # Don't allow updates to cancelled or completed meetings
            if meeting.get("status") in [MeetingStatus.CANCELLED.value, MeetingStatus.COMPLETED.value]:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Cannot update {meeting.get('status')} meeting"
                )
            
            update_data = {}
            
            if payload.title is not None:
                update_data["title"] = payload.title
            if payload.description is not None:
                update_data["description"] = payload.description
            if payload.scheduled_time is not None:
                # Validate scheduled time is in the future
                now = int(datetime.utcnow().timestamp())
                if payload.scheduled_time <= now:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        "Scheduled time must be in the future"
                    )
                update_data["scheduled_time"] = payload.scheduled_time
            if payload.duration_minutes is not None:
                update_data["duration_minutes"] = payload.duration_minutes
            if payload.status is not None:
                update_data["status"] = payload.status.value
            
            # Update Google Calendar event if needed
            calendar_event_id = meeting.get("google_calendar_event_id")
            if calendar_event_id and self.google_calendar.service and update_data:
                start_time = None
                end_time = None
                
                scheduled_time = update_data.get("scheduled_time", meeting.get("scheduled_time"))
                duration = update_data.get("duration_minutes", meeting.get("duration_minutes"))
                
                if scheduled_time:
                    start_time = datetime.fromtimestamp(scheduled_time)
                    end_time = start_time + timedelta(minutes=duration)
                
                client_email = meeting.get("client", {}).get("email")
                freelancer_email = meeting.get("freelancer", {}).get("email")
                attendees = []
                if client_email:
                    attendees.append(client_email)
                if freelancer_email:
                    attendees.append(freelancer_email)
                
                google_event = self.google_calendar.update_meeting(
                    event_id=calendar_event_id,
                    title=update_data.get("title") or meeting.get("title"),
                    description=update_data.get("description") or meeting.get("description"),
                    start_time=start_time,
                    end_time=end_time,
                    attendees=attendees if attendees else None,
                    timezone=meeting.get("timezone", "UTC")
                )
                
                if google_event:
                    if google_event.get("meet_link"):
                        update_data["google_meet_link"] = google_event.get("meet_link")
                    logger.info("Google Calendar event updated: %s", calendar_event_id)
            
            updated_meeting = self.repo.update(meeting_id, update_data)
            if not updated_meeting:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting")
            
            logger.info("Meeting updated: %s", meeting_id)
            return updated_meeting
            
        except HTTPException:
            raise
        except PyMongoError as e:
            logger.exception("Database error updating meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting")
        except Exception as e:
            logger.exception("Error updating meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting")
    
    def cancel_meeting(self, meeting_id: str, cancelled_by: str) -> Dict[str, Any]:
        """Cancel a meeting"""
        try:
            meeting = self.repo.get_by_id(meeting_id)
            if not meeting:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")
            
            # Verify user is part of the agreement
            if cancelled_by not in [
                meeting.get("client", {}).get("user_id"),
                meeting.get("freelancer", {}).get("user_id")
            ]:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not authorized to cancel this meeting"
                )
            
            # Don't allow cancelling already cancelled or completed meetings
            if meeting.get("status") == MeetingStatus.CANCELLED.value:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Meeting is already cancelled"
                )
            
            if meeting.get("status") == MeetingStatus.COMPLETED.value:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Cannot cancel a completed meeting"
                )
            
            # Cancel Google Calendar event
            calendar_event_id = meeting.get("google_calendar_event_id")
            if calendar_event_id and self.google_calendar.service:
                self.google_calendar.cancel_meeting(calendar_event_id)
                logger.info("Google Calendar event cancelled: %s", calendar_event_id)
            
            # Cancel meeting in database
            cancelled_meeting = self.repo.cancel(meeting_id, cancelled_by)
            if not cancelled_meeting:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel meeting")
            
            logger.info("Meeting cancelled: %s by %s", meeting_id, cancelled_by)
            return cancelled_meeting
            
        except HTTPException:
            raise
        except PyMongoError as e:
            logger.exception("Database error cancelling meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel meeting")
        except Exception as e:
            logger.exception("Error cancelling meeting: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel meeting")
    
    def get_filtered_meetings(self, filter: MeetingFilter) -> List[Dict[str, Any]]:
        """Get meetings with filters"""
        if filter.agreement_id:
            return self.repo.get_by_agreement(filter.agreement_id, filter.upcoming_only or False)
        elif filter.user_id:
            return self.repo.get_by_user(filter.user_id, filter.upcoming_only or False)
        else:
            # Return all upcoming meetings if no filter
            return self.repo.get_upcoming_meetings(limit=50)
    
    def update_meeting_link(
        self,
        meeting_id: str,
        meet_link: str,
        updated_by: str
    ) -> Dict[str, Any]:
        """Update meeting link manually"""
        try:
            meeting = self.repo.get_by_id(meeting_id)
            if not meeting:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")
            
            # Verify user is part of the agreement
            if updated_by not in [
                meeting.get("client", {}).get("user_id"),
                meeting.get("freelancer", {}).get("user_id")
            ]:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not authorized to update this meeting"
                )
            
            # Validate link format (basic validation)
            if not meet_link.startswith(("http://", "https://")):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Invalid meeting link format. Must be a valid URL."
                )
            
            # Update meeting link
            updated_meeting = self.repo.update(meeting_id, {"google_meet_link": meet_link})
            if not updated_meeting:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting link")
            
            logger.info("Meeting link updated: %s by %s", meeting_id, updated_by)
            return updated_meeting
            
        except HTTPException:
            raise
        except PyMongoError as e:
            logger.exception("Database error updating meeting link: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting link")
        except Exception as e:
            logger.exception("Error updating meeting link: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update meeting link")


