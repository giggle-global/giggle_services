"""
Google Calendar API service for creating meetings with Google Meet links
"""
import os
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import config

logger = logging.getLogger(__name__)

# Google Calendar API scopes - Required for creating Google Meet links
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Check if running in production
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() in ["production", "prod"] or \
                os.environ.get("GOOGLE_USE_SERVICE_ACCOUNT", "").lower() == "true"


class GoogleCalendarService:
    """Service for interacting with Google Calendar API"""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _validate_scopes(self, creds: Credentials) -> bool:
        """Validate that credentials have the required scopes"""
        if not creds or not creds.scopes:
            return False
        
        required_scope = 'https://www.googleapis.com/auth/calendar'
        has_scope = any(required_scope in scope for scope in creds.scopes)
        
        if not has_scope:
            logger.error("Credentials missing required scope: %s. Available scopes: %s", required_scope, creds.scopes)
            return False
        
        return True
    
    def _initialize_service(self):
        """Initialize Google Calendar service"""
        try:
            # Check for credentials from environment variables first (production-friendly)
            google_credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            google_service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
            google_token_json = os.environ.get("GOOGLE_TOKEN_JSON")
            
            # Fallback to file paths if env vars not set (for local development)
            credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
            token_path = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")
            service_account_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "service_account.json")
            
            # In production, prefer Service Account (no user interaction needed)
            # Try environment variable first, then file path
            if google_service_account_json:
                logger.info("Using Service Account from GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
                try:
                    import json
                    service_account_info = json.loads(google_service_account_json)
                    creds = service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=SCOPES
                    )
                    self.service = build('calendar', 'v3', credentials=creds)
                    logger.info("Google Calendar service initialized successfully with Service Account (from env var)")
                    return
                except Exception as e:
                    logger.error("Failed to initialize Service Account from env var: %s. Trying file path.", str(e))
                    logger.exception("Service Account error details:")
            
            # Try service account file if env var not available
            if IS_PRODUCTION and os.path.exists(service_account_path):
                logger.info("Production environment detected. Using Service Account for Google Calendar.")
                try:
                    creds = service_account.Credentials.from_service_account_file(
                        service_account_path,
                        scopes=SCOPES
                    )
                    self.service = build('calendar', 'v3', credentials=creds)
                    logger.info("Google Calendar service initialized successfully with Service Account")
                    return
                except Exception as e:
                    logger.error("Failed to initialize Service Account: %s. Falling back to OAuth.", str(e))
                    logger.exception("Service Account error details:")
            
            # Check if we have a pre-authenticated token (works in production if token.json exists)
            creds = None
            
            # Load existing token from environment variable first
            if google_token_json:
                try:
                    import json
                    token_data = json.loads(google_token_json)
                    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                    if not self._validate_scopes(creds):
                        logger.warning("Token from env var has invalid scopes. Will try to create new credentials.")
                        creds = None
                    else:
                        logger.info("Loaded token from GOOGLE_TOKEN_JSON environment variable.")
                except Exception as e:
                    logger.warning("Failed to load token from env var: %s. Trying file path.", str(e))
                    creds = None
            
            # Load existing token from file if env var not available
            if not creds and os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                    if not self._validate_scopes(creds):
                        logger.warning("Token file has invalid scopes. Will try to create new credentials.")
                        creds = None
                except Exception as e:
                    logger.warning("Failed to load existing token file: %s. Will try to create new credentials.", str(e))
                    creds = None
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        if not self._validate_scopes(creds):
                            logger.warning("Refreshed token has invalid scopes. Will try to create new credentials.")
                            creds = None
                    except Exception as e:
                        logger.warning("Failed to refresh token: %s. Will try to create new credentials.", str(e))
                        creds = None
                
                if not creds or not creds.valid:
                    # Try to load credentials from environment variable first
                    creds_data = None
                    if google_credentials_json:
                        try:
                            import json
                            creds_data = json.loads(google_credentials_json)
                            logger.info("Loaded credentials from GOOGLE_CREDENTIALS_JSON environment variable.")
                        except Exception as e:
                            logger.error("Failed to parse GOOGLE_CREDENTIALS_JSON: %s", str(e))
                            creds_data = None
                    
                    # Fallback to file if env var not available
                    if not creds_data and os.path.exists(credentials_path):
                        try:
                            import json
                            with open(credentials_path, 'r') as f:
                                creds_data = json.load(f)
                        except Exception as e:
                            logger.warning("Could not read credentials file: %s", str(e))
                            creds_data = None
                    
                    if not creds_data:
                        logger.warning("Google credentials not found in environment variable or file. Meeting creation will proceed without Google Meet links.")
                        self.service = None
                        return
                    
                    # Check if credentials file is for Web app or Desktop app
                    is_web_app = 'web' in creds_data
                    is_desktop_app = 'installed' in creds_data
                    
                    # Support both web and desktop app credentials
                    if is_web_app and not is_desktop_app:
                        logger.info("Web application credentials detected. Using web OAuth flow.")
                        # For web app, we need to use a different flow, but since we have token.json,
                        # we can skip the OAuth flow and just use the token
                        # The token.json should already have the necessary credentials
                        logger.info("Using existing token.json for authentication.")
                    elif not is_desktop_app and not is_web_app:
                        logger.error("Invalid credentials format. Expected 'web' or 'installed' key.")
                        self.service = None
                        return
                    
                    try:
                        # For web app credentials, we can't use InstalledAppFlow
                        # Since we have token.json, we should have already loaded credentials above
                        # If we reach here, it means token refresh failed, so we need to re-authenticate
                        if is_web_app:
                            logger.error("=" * 80)
                            logger.error("WEB APP CREDENTIALS DETECTED")
                            logger.error("=" * 80)
                            logger.error("Web app credentials require a different OAuth flow.")
                            logger.error("Since token.json exists, authentication should work via token refresh.")
                            logger.error("If you're seeing this, the token may have expired.")
                            logger.error("")
                            logger.error("SOLUTION: Re-authenticate locally and update GOOGLE_TOKEN_JSON")
                            logger.error("=" * 80)
                            self.service = None
                            return
                        
                        # Use from_client_config instead of from_client_secrets_file when we have JSON data
                        if google_credentials_json:
                            flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                        else:
                            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                        
                        # In production, we can't use run_local_server (no browser/user interaction)
                        if IS_PRODUCTION:
                            logger.error("=" * 80)
                            logger.error("PRODUCTION ENVIRONMENT DETECTED")
                            logger.error("=" * 80)
                            logger.error("OAuth flow requires user interaction (browser), which is not available in production.")
                            logger.error("")
                            logger.error("SOLUTIONS:")
                            logger.error("1. Use Service Account (Recommended for production):")
                            logger.error("   - Create Service Account in Google Cloud Console")
                            logger.error("   - Download service account JSON key")
                            logger.error("   - Save as 'service_account.json' in your project root")
                            logger.error("   - Set GOOGLE_SERVICE_ACCOUNT_PATH environment variable")
                            logger.error("   - Grant Calendar API access to the service account")
                            logger.error("")
                            logger.error("2. Pre-authenticate locally and copy token.json:")
                            logger.error("   - Run authentication locally (creates token.json)")
                            logger.error("   - Copy token.json to production server")
                            logger.error("   - Ensure token.json is in the correct path")
                            logger.error("=" * 80)
                            self.service = None
                            return
                        
                        # Use a fixed port for OAuth redirect (default: 8080)
                        # For Desktop apps, Google automatically allows localhost with any port
                        oauth_port = int(os.environ.get("GOOGLE_OAUTH_PORT", "8080"))
                        
                        logger.info("Starting OAuth flow on port %d. Please authorize in the browser.", oauth_port)
                        logger.info("If you see 'redirect_uri_mismatch' error, ensure your OAuth client type is 'Desktop app' in Google Cloud Console")
                        
                        # Development: Use local server for OAuth
                        creds = flow.run_local_server(
                            port=oauth_port,
                            open_browser=True,
                            redirect_uri_trailing_slash=False
                        )
                        
                        if not self._validate_scopes(creds):
                            logger.error("New credentials have invalid scopes. Cannot create Google Meet links.")
                            self.service = None
                            return
                    except Exception as e:
                        error_msg = str(e)
                        if "redirect_uri_mismatch" in error_msg.lower() or "400" in error_msg:
                            logger.error("=" * 80)
                            logger.error("OAUTH CONFIGURATION ERROR: redirect_uri_mismatch")
                            logger.error("=" * 80)
                            logger.error("Your credentials.json appears to be for a 'Web application'.")
                            logger.error("This code requires 'Desktop app' credentials.")
                            logger.error("")
                            logger.error("To fix this:")
                            logger.error("1. Go to: https://console.cloud.google.com/apis/credentials")
                            logger.error("2. Create a NEW OAuth client with type 'Desktop app'")
                            logger.error("3. Download the new credentials.json file")
                            logger.error("4. Replace your current credentials.json")
                            logger.error("=" * 80)
                        else:
                            logger.error("Failed to obtain Google credentials: %s", error_msg)
                        logger.exception("Full error details:")
                        self.service = None
                        return
                
                # Save credentials for next run (only if using file-based token, not env var)
                if creds and not google_token_json:
                    try:
                        # Only save to file if token_path is writable (local development)
                        if not IS_PRODUCTION or os.path.exists(os.path.dirname(token_path)):
                            with open(token_path, 'w') as token:
                                token.write(creds.to_json())
                            logger.info("Token saved to file. For production, consider using GOOGLE_TOKEN_JSON environment variable instead.")
                    except Exception as e:
                        logger.warning("Failed to save token file: %s. In production, use GOOGLE_TOKEN_JSON environment variable.", str(e))
            
            if creds and self._validate_scopes(creds):
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar service initialized successfully with required scopes")
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
            raise Exception("Google Calendar service not initialized. Please configure Google Calendar API credentials.")
        
        try:
            # Generate unique request ID for conference creation
            unique_request_id = f"meet-{uuid.uuid4().hex[:16]}-{int(datetime.utcnow().timestamp())}"
            
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
                'attendees': [{'email': email} for email in attendees] if attendees else [],
                'conferenceData': {
                    'createRequest': {
                        'requestId': unique_request_id,
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
            
            logger.info("Creating Google Calendar event with Meet link (requestId: %s)", unique_request_id)
            
            # Create the event with conferenceDataVersion=1 to ensure Meet link is created
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1  # Required to create Meet link
            ).execute()
            
            # Extract Meet link - check multiple possible locations
            meet_link = None
            
            # Method 1: Check hangoutLink (direct property)
            if created_event.get('hangoutLink'):
                meet_link = created_event.get('hangoutLink')
                logger.info("Found Meet link in hangoutLink: %s", meet_link)
            
            # Method 2: Check conferenceData.entryPoints
            elif 'conferenceData' in created_event:
                conference_data = created_event['conferenceData']
                entry_points = conference_data.get('entryPoints', [])
                
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        logger.info("Found Meet link in entryPoints: %s", meet_link)
                        break
                
                # If still no link, check conferenceSolution
                if not meet_link and 'conferenceSolution' in conference_data:
                    solution = conference_data['conferenceSolution']
                    if 'entryPoints' in solution:
                        for entry in solution['entryPoints']:
                            if entry.get('entryPointType') == 'video':
                                meet_link = entry.get('uri')
                                logger.info("Found Meet link in conferenceSolution: %s", meet_link)
                                break
            
            # Validate that we got a Meet link
            if not meet_link:
                error_msg = "Google Calendar event created but no Meet link was returned in the response"
                logger.error(error_msg)
                logger.error("Event response: %s", str(created_event))
                
                # Check for common error scenarios
                if 'conferenceData' not in created_event:
                    error_msg += ". conferenceData is missing from response."
                elif 'createRequest' in created_event.get('conferenceData', {}):
                    error_msg += ". Conference request was sent but no link was generated."
                
                raise Exception(error_msg)
            
            # Validate Meet link format
            if not meet_link.startswith('https://meet.google.com/'):
                logger.warning("Meet link doesn't match expected format: %s", meet_link)
            
            logger.info("Google Calendar event created successfully: %s with Meet link: %s", 
                       created_event.get('id'), meet_link)
            
            return {
                'event_id': created_event.get('id'),
                'meet_link': meet_link,
                'html_link': created_event.get('htmlLink'),
                'hangout_link': meet_link,  # Use meet_link as hangout_link for consistency
            }
            
        except HttpError as e:
            error_details = e.error_details if hasattr(e, 'error_details') else str(e)
            logger.error("Google Calendar API HttpError: %s - %s", e.resp.status, error_details)
            
            # Provide more specific error messages
            if e.resp.status == 403:
                raise Exception("Google Calendar API access denied. Please check OAuth scopes and permissions.")
            elif e.resp.status == 401:
                raise Exception("Google Calendar API authentication failed. Please refresh your credentials.")
            elif e.resp.status == 400:
                raise Exception(f"Invalid request to Google Calendar API: {error_details}")
            else:
                raise Exception(f"Google Calendar API error ({e.resp.status}): {error_details}")
                
        except Exception as e:
            error_msg = f"Error creating Google Calendar event: {str(e)}"
            logger.exception(error_msg)
            raise Exception(error_msg)
    
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

