import logging 
from langchain_core.tools import tool
from datetime import datetime, timedelta, timezone as DateTimeTz
from typing import List, Dict, Any, Optional
from pathlib import Path
from google.auth.transport.requests import Request 
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.config import Config, project_root

logger = logging.getLogger(__name__)

# if modifying scopes, delete the file token.json
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService: 
    def __init__(self):
        self.creds = None 
        self.service = None
        self.token_path = Path(Config.DATA_DIR) / 'goog_token.json'
        self._authenticate()
        
    def _authenticate(self):
        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing Google Calendar credentials.")
                self.creds.refresh(Request())
            else:
                logger.info("Starting new Authentication flow for Google Calendar.")
                credentials_path = Path(project_root) / Config.GOOGLE_CALENDAR_CREDENTIALS_PATH
                if not credentials_path.exists():
                    logger.error(f"Credentials file not found at {credentials_path}")
                    raise FileNotFoundError(
                        f"Credentials file not found at {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
            logger.info(f"Saved new credentials to {self.token_path}")
        self.service = build('calendar', 'v3', credentials=self.creds)
        logger.info("Google Calendar service initialized.")
        
    def create_event(self,
                     summary: str,
                     start_time: datetime,
                     end_time: datetime,
                     description: Optional[str] = None,
                     location: Optional[str] = None,
                     attendees: Optional[List[str]] = None,
                     timezone: str = 'America/New_York') -> Dict[str, Any]:
        try:
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone
                },
            }
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            created_event = self.service.events().insert(
                calendarId = 'primary',
                body = event
            ).execute()
            
            logger.info(f"Event created: {created_event.get('htmlLink')}")
            return created_event
        
        except HttpError as error:
            logger.error(f"An error occurred while creating event: {error}")
            raise
    
    def list_events(
        self, 
        max_results: int = 10,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        try: 
            if time_min is None:
                time_min = datetime.now(DateTimeTz.utc)
            params = {
                'calendarId': 'primary',
                'timeMin': time_min.isoformat().replace('+00:00', 'Z'),
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            if time_max:
                params['timeMax'] = time_max.isoformat().replace('+00:00', 'Z')
            events_result = self.service.events().list(**params).execute()
            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} events")
            return events
            
            
        except Exception as e:
            logger.error(f"An error occurred while listing events: {e}")
            raise
    
    def get_event(self, event_id: str) -> Dict[str, Any]:
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            logger.info(f"Retrieved event: {event.get('summary')}")
            return event
        except HttpError as error:
            logger.error(f"An error occurred while getting an event: {error}")
            raise
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = 'America/New_York'
    ) -> Dict[str, Any]:
        try:
            event = self.get_event(event_id=event_id)
            if summary:
                event["summary"] = summary 
            if start_time:
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone
                }
            if end_time:
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone
                }
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event
            ).execute()
            logger.info(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event
        except HttpError as error:
            logger.error(f"An error occurred while updating event: {error}") 
            raise 
    
    def delete_event(self, event_id: str) -> bool:
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id,
            ).execute()
            logger.info(f"Event deleted: {event_id}")
            return True 
        except HttpError as error:
            logger.error(f"An error occurred while deleting event: {error}") 
            raise  
        
    def search_events(
        self, 
        query: str,
        max_results: int = 10,
        time_min: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        try:
            if time_min is None:
                time_min = datetime.utcnow()
            event_result = self.service.events().list(
                calendarId='primary',
                q=query,
                timeMin=time_min.isoformat().replace('+00:00', 'Z'),
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = event_result.get('items', [])
            logger.info(f"Found {len(events)} events matching the query '{query}'")
            return events 
        except HttpError as error:
            logger.error(f"An error occured while searching events: {error}")
            raise
        
_goog_calendar_service = None 

def get_goog_calendar_service() -> GoogleCalendarService:
    global _goog_calendar_service    
    if _goog_calendar_service is None:
        _goog_calendar_service = GoogleCalendarService()
    return _goog_calendar_service
    

@tool
def create_google_calendar_event(
    summary: str,
    start_time: str, 
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = 'America/New_York') -> str:
    """
    Create a new calendar event in Google Calendar.
    
    Args:
        summary: The event title/summary
        start_time: Start time in ISO format WITH timezone offset (e.g., "2026-01-05T14:00:00-05:00" for EST)
        end_time: End time in ISO format WITH timezone offset. If not provided, defaults to 1 hour after start
        description: Optional event description
        location: Optional event location
        timezone: Timezone name for the event (default: America/New_York)
    
    Returns:
        Success message with event details
    """
    try:
        calendar_service = get_goog_calendar_service()
        
        start_dt = datetime.fromisoformat(start_time.replace('Z', "+00:00"))
        
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', "+00:00"))
        else:
            end_dt = start_dt + timedelta(hours=1)
        
        calendar_service.create_event(
            summary=summary,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            location=location,
            timezone=timezone
        )
        
        result = f"✓ Event created: '{summary}' on {start_dt.strftime('%Y-%m-%d at %H:%M')}"
        return result 
    except Exception as e:
        logger.error(f"Error in create_google_calendar_event tool: {e}", exc_info=True)
        return f"Error creating event: {str(e)}"
    
@tool 
def list_google_calendar_events(max_results: int=10) -> str:
    """
    List upcoming calendar events from Google Calendar.
    
    Args:
        max_results: Maximum number of events to return (default: 10)
    
    Returns:
        Formatted list of upcoming events
    """
    try: 
        calendar_service = get_goog_calendar_service()
        events = calendar_service.list_events(max_results=max_results)
        
        if not events:
            return "No upcoming events found."
    
        result = f"Upcoming events ({len(events)}): \n\n"
        
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            result += f"{i}. {event['summary']}\n   📅 {start}\n"
            
            if event.get("location"):
                result += f"   📍 {event['location']}\n"
            if event.get("description"):
                desc = event["description"]
                result += f"   📝 {desc[:50]}...\n" if len(desc) > 50 else f"   📝 {desc}\n"
            result += "\n"
            
        return result 

    except Exception as e:
        logger.error(f"Error in listing Google Calendar events: {e}")
        return f"Error listing events: {str(e)}" 
    

@tool
def search_google_calendar_events(query: str, max_results: int = 5) -> str:
    """
    Search for calendar events by keyword in Google Calendar.
    
    Args:
        query: Search query string (searches event titles, descriptions, locations)
        max_results: Maximum number of results (default: 5)
    
    Returns:
        Formatted list of matching events
    """
    try:
        calendar_service = get_goog_calendar_service()
        events = calendar_service.search_events(query=query, max_results=max_results)
        
        if not events:
            return f"No events found matching '{query}'."
        
        result = f"Events matching '{query}' ({len(events)}):\n\n"
        for i, event in enumerate(events, 1):
            start = event['start'].get("dateTime", event['start'].get('date'))
            result +=  f"{i}. {event['summary']}\n   📅 {start}\n"
            if event.get('location'):
                result += f"   📍 {event['location']}\n"
            result += "\n"
        return result
 
    except Exception as e:
        logger.error(f"Error in searching Google Calendar events: {e}")
        return f"Error searching events: {str(e)}" 
    
@tool
def update_google_calendar_event(
    event_id: str,
    summary: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = 'America/New_York'
) -> str:
    """
    Update an existing Google Calendar event.

    Args:
        event_id: The ID of the event to update
        summary: New event title (optional)
        start_time: New start time in ISO format WITH timezone offset (optional)
        end_time: New end time in ISO format WITH timezone offset (optional)
        description: New event description (optional)
        location: New event location (optional)
        timezone: Timezone for the event (default: America/New_York)
    
    Returns:
        Success message with updated event details
    """
    try:
        calendar_service = get_goog_calendar_service()
        
        start_dt = None
        end_dt = None 
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', "+00:00"))
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', "+00:00"))
        
        updated_event = calendar_service.update_event(
            event_id=event_id,
            summary=summary,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            location=location,
            timezone=timezone
        )
        
        result = f"✓ Event updated: '{updated_event.get('summary')}'"
        return result
    
    except Exception as error:
        logger.error(f"Error in update_google_calendar_event tool: {error}", exc_info=True)
        return f"Error updating event: {str(error)}"

@tool
def delete_google_calendar_event(event_id: str) -> str:
    """
    Delete a Google Calendar event.
    
    Args:
        event_id: The ID of the event to delete
    
    Returns:
        Success message confirming deletion
    """
    try:
        calendar_service = get_goog_calendar_service()
        event = calendar_service.get_event(event_id=event_id)
        event_title = event.get('summary', 'Untitled Event')
        
        calendar_service.delete_event(event_id=event_id)
        
        result = f"✓ Event deleted: '{event_title}'"
        return result
        
    except Exception as e:
        logger.error(f"Error in delete_google_calendar_event tool: {e}", exc_info=True)
        return f"Error deleting event: {str(e)}"