"""
Google Calendar API service for creating meetings with Google Meet links
"""
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import config

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']


class GoogleCalendarService:
    """Service for interacting with Google Calendar API"""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service"""
        try:
            # Check if credentials file exists
            credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
            token_path = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")
            
            creds = None
            
            # Load existing token if available
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                except Exception as e:
                    logger.warning("Failed to load existing token file: %s. Will try to create new credentials.", str(e))
                    creds = None
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning("Failed to refresh token: %s. Will try to create new credentials.", str(e))
                        creds = None
                
                if not creds or not creds.valid:
                    if not os.path.exists(credentials_path):
                        logger.warning("Google credentials file not found at %s. Meeting creation will proceed without Google Meet links.", credentials_path)
                        self.service = None
                        return
                    
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                        # Note: run_local_server requires user interaction, which may not be available in production
                        # In production, consider using service account credentials instead
                        creds = flow.run_local_server(port=0)
                    except Exception as e:
                        logger.error("Failed to obtain Google credentials: %s. Meeting creation will proceed without Google Meet links.", str(e))
                        self.service = None
                        return
                
                # Save credentials for next run
                if creds:
                    try:
                        with open(token_path, 'w') as token:
                            token.write(creds.to_json())
                    except Exception as e:
                        logger.warning("Failed to save token file: %s", str(e))
            
            if creds:
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar service initialized successfully")
            else:
                self.service = None
                logger.warning("Google Calendar service not initialized. Meeting creation will proceed without Google Meet links.")
            
        except Exception as e:
            logger.error("Failed to initialize Google Calendar service: %s. Meeting creation will proceed without Google Meet links.", e)
            logger.exception("Full exception details:")
            self.service = None
    
    def create_meeting(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        timezone: str = "UTC"
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Google Calendar event with Google Meet link
        
        Args:
            title: Meeting title
            description: Meeting description
            start_time: Meeting start time (datetime object)
            end_time: Meeting end time (datetime object)
            attendees: List of attendee email addresses
            timezone: Timezone string (default: UTC)
        
        Returns:
            Dictionary with event details including meet link, or None if failed
        """
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None
        
        try:
            # Create event with Google Meet conference
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone,
                },
                'attendees': [{'email': email} for email in attendees],
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meet-{datetime.utcnow().timestamp()}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 24 hours before
                        {'method': 'popup', 'minutes': 15},  # 15 minutes before
                    ],
                },
            }
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1  # Required to create Meet link
            ).execute()
            
            # Extract Meet link
            meet_link = None
            if 'conferenceData' in created_event:
                entry_points = created_event['conferenceData'].get('entryPoints', [])
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        break
            
            logger.info("Google Calendar event created: %s", created_event.get('id'))
            
            return {
                'event_id': created_event.get('id'),
                'meet_link': meet_link,
                'html_link': created_event.get('htmlLink'),
                'hangout_link': created_event.get('hangoutLink'),
            }
            
        except HttpError as e:
            logger.error("Google Calendar API error: %s", e)
            return None
        except Exception as e:
            logger.exception("Error creating Google Calendar event: %s", e)
            return None
    
    def update_meeting(
        self,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC"
    ) -> Optional[Dict[str, Any]]:
        """Update an existing Google Calendar event"""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None
        
        try:
            # Get existing event
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Update fields
            if title:
                event['summary'] = title
            if description:
                event['description'] = description
            if start_time:
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone,
                }
            if end_time:
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone,
                }
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event,
                conferenceDataVersion=1
            ).execute()
            
            # Extract Meet link
            meet_link = None
            if 'conferenceData' in updated_event:
                entry_points = updated_event['conferenceData'].get('entryPoints', [])
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        break
            
            logger.info("Google Calendar event updated: %s", event_id)
            
            return {
                'event_id': updated_event.get('id'),
                'meet_link': meet_link,
                'html_link': updated_event.get('htmlLink'),
            }
            
        except HttpError as e:
            logger.error("Google Calendar API error updating event: %s", e)
            return None
        except Exception as e:
            logger.exception("Error updating Google Calendar event: %s", e)
            return None
    
    def cancel_meeting(self, event_id: str) -> bool:
        """Cancel/delete a Google Calendar event"""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return False
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            logger.info("Google Calendar event deleted: %s", event_id)
            return True
        except HttpError as e:
            logger.error("Google Calendar API error deleting event: %s", e)
            return False
        except Exception as e:
            logger.exception("Error deleting Google Calendar event: %s", e)
            return False

