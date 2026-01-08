import logging 
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from caldav import DAVClient, Calendar
from caldav.lib.error import DAVError
from langchain_core.tools import tool 
from icalendar import Calendar as iCalendar, Event as IEvent 
import pytz
from src.config import Config 

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self, username: str, password: str):
        """
        Initialize CalDAV calendar service for iCloud only.

        Args:
            username: iCloud email/Apple ID
            password: App-specific password from appleid.apple.com
        """
        self.provider = "icloud"
        url = "https://caldav.icloud.com/"

        try:
            self.client = DAVClient(url=url, username=username, password=password)
            self.principal = self.client.principal()
            calendars = self.principal.calendars()
            self.calendar = None

            if not calendars:
                raise Exception(f"No calendars found")
            for cal in calendars:
                if cal.name == "Home":
                    self.calendar = cal
                    break
            if not self.calendar:
                raise Exception(f"'Home' calendar not found. Available calendars: {[c.name for c in calendars]}")
            
            logger.info(f"Connected to iCloud calendar: {self.calendar.name}")

        except Exception as e:
            logger.error(f"Failed to connect to iCloud calendar: {e}")
            raise

    def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = 'America/New_York',
        reminder_minutes: int = 30
    ) -> Dict[str, Any]:
        try:
            cal = iCalendar()
            cal.add('prodid', '-//Personal Assistant Agent//EN')
            cal.add('version', '2.0')

            event = IEvent()

            tz = pytz.timezone(timezone)

            if start_time.tzinfo is None:
                start_time = tz.localize(start_time)
            if end_time.tzinfo is None:
                end_time = tz.localize(end_time)


            event.add('summary', summary)
            event.add('dtstart', start_time)
            event.add('dtend', end_time)
            event.add('uid', f'{datetime.now().timestamp()}@personal-assistant')
            event.add('dtstamp', datetime.now(pytz.utc))

            if description:
                event.add('description', description)
            if location:
                event.add('location', location)
                
            if reminder_minutes > 0:
                from icalendar import Alarm
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('trigger', timedelta(minutes=-reminder_minutes))
                alarm.add('description', f'Reminder: {summary}')
                event.add_component(alarm)
                second_alarm = Alarm()
                second_alarm.add('action', 'DISPLAY')
                second_alarm.add('trigger', timedelta(days=1))
                second_alarm.add('description', f'Reminder: {summary}')
                event.add_component(second_alarm)
                

            cal.add_component(event)

            ical_string = cal.to_ical().decode('utf-8')
            created_event = self.calendar.save_event(ical_string)
            logger.info(f"Event created in {self.provider}: {summary}")

            return {
                'summary': summary,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'id': str(created_event.id),
                'provider': self.provider
            }
        except Exception as e:
            logger.error(f"Error creating event in {self.provider}: {e}")
            raise

    def list_events(
        self,
        max_results: int = 10,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        try:
            if time_min is None:
                time_min = datetime.now()
            if time_max is None:
                time_max = time_min + timedelta(days=30)

            events = self.calendar.date_search(
                start=time_min,
                end=time_max,
                expand=True
            )
            results = []

            for event in events[:max_results]:
                vev = event.vobject_instance.vevent
                results.append({
                    'summary': str(vev.summary.value),
                    'start': vev.dtstart.value.isoformat() if hasattr(vev, 'dtstart') else None,
                    'end': vev.dtend.value.isoformat() if hasattr(vev, 'dtend') else None,
                    'description': vev.description.value if hasattr(vev, 'description') else None,
                    'location': vev.location.value if hasattr(vev, 'location') else None,
                    'id': str(event.url),
                    'provider': self.provider
                })

            logger.info(f"Retrieved {len(results)} events from {self.provider}")
            return results

        except Exception as e:
            logger.error(f"Error listing events from {self.provider}: {e}")
            return []

    def search_events(
        self,
        query: str,
        max_results: int = 10,
        time_min: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        try:
            if time_min is None:
                time_min = datetime.now()

            time_max = time_min + timedelta(days=365)

            events = self.calendar.date_search(
                start=time_min,
                end=time_max,
                expand=True
            )

            results = []
            for event in events:
                vev = event.vobject_instance.vevent
                summary = str(vev.summary.value) if hasattr(vev, 'summary') else ""
                description = str(vev.description.value) if hasattr(vev, 'description') else ""

                if query.lower() in summary.lower() or query.lower() in description.lower():
                    results.append({
                        'summary': summary,
                        'start': vev.dtstart.value.isoformat() if hasattr(vev, 'dtstart') else None,
                        'end': vev.dtend.value.isoformat() if hasattr(vev, 'dtend') else None,
                        'description': description,
                        'location': vev.location.value if hasattr(vev, 'location') else None,
                        'id': str(event.url),
                        'provider': self.provider
                    })

                    if len(results) >= max_results:
                        break

            logger.info(f"Found {len(results)} events matching '{query}' in {self.provider}")
            return results

        except Exception as e:
            logger.error(f"Error searching events in {self.provider}: {e}")
            return []

    def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID."""
        try:
            event = self.calendar.event_by_url(event_id)
            event.delete()
            logger.info(f"Event deleted from {self.provider}: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting event from {self.provider}: {e}")
            raise

def get_all_calendars() -> List[CalendarService]:
    calendars = []

    if Config.ICLOUD_EMAIL and Config.ICLOUD_APP_PASSWORD:
        try:
            icloud_cal = CalendarService(
                username=Config.ICLOUD_EMAIL,
                password=Config.ICLOUD_APP_PASSWORD
            )
            calendars.append(icloud_cal)
        except Exception as e:
            logger.warning(f"Could not connect to iCloud Calendar: {e}")

    return calendars

@tool
def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    timezone: str = "America/New_York"
) -> str:
    """
    Create a calendar event in iCloud calendar.
    Args:
        summary: Event title
        start_time: ISO format datetime string (e.g., "2024-01-15T14:00:00")
        end_time: ISO format datetime string
        description: Event description
        location: Event location
        timezone: Timezone (default: America/New_York)
    Returns:
        Success message
    """
    calendars = get_all_calendars()
    
    if not calendars:
        return "Error: No iCloud calendar configured. Please set up iCloud credentials."

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    calendar = calendars[0]

    try:
        calendar.create_event(
            summary=summary,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            location=location,
            timezone=timezone,
        )
        return f"🍎 Event '{summary}' created in iCloud calendar"
    except Exception as e:
        return f"❌ Error creating event: {str(e)}"

@tool
def list_calendar_events(max_results: int = 10) -> str:
    """
    List upcoming events from iCloud calendar.
    Args:
        max_results: Maximum number of events per calendar (default: 10)
    Returns:
        Formatted list of events with 🍎 icon
    """
    calendars = get_all_calendars()
    if not calendars:
        return "No calendars configured"
    all_events = []
    
    for calendar in calendars:
        try:
            events = calendar.list_events(max_results=max_results)
            icon = "📧" if calendar.provider == "google" else "🍎"
            for event in events:
                event['provider_icon'] = icon
                all_events.append(event)
        except Exception as e:
            logger.error(f"Error listing events from {calendar.provider}: {e}")
            
    if not all_events:
        return "No upcoming events found."
    
    all_events.sort(key=lambda e: e.get('start', ''))
    result = "Upcoming events: \n"
    for event in all_events:
        result += f"\n   ID: {event['id']}"
        result += f"\n{event['provider_icon']} {event['summary']}"
        if event.get('start'):
            result += f"\n   Time: {event['start']}"
        if event.get('location'):
            result += f"\n   Location: {event['location']}"
        if event.get('description'):
            result += f"\n   Description: {event['description']}"
        result += "\n"
    return result

@tool
def search_calendar_events(query:str, max_results: int = 10) -> str:
    """
    Search for events in iCloud calendar.
    Args:
        query: Search query to match against event titles and descriptions
        max_results: Maximum number of results per calendar (default: 10)
    Returns:
        Formatted list of matching events with 🍎 icon
    """
    calendars = get_all_calendars()
    if not calendars:
        return "No calendars configured"

    all_events = []
    
    for calendar in calendars:
        try: 
            events = calendar.search_events(query=query, max_results=max_results)
            icon = "📧" if calendar.provider == "google" else "🍎"
            for event in events:
                event['provider_icon'] = icon
                all_events.append(event)
        except Exception as e:
            logger.error(f"Error searching events in {calendar.provider}: {e}")
            
    if not all_events:
        return f"No events found matching '{query}'."
    
    all_events.sort(key=lambda e: e.get("start", ""))
    result = f"Events matching '{query}': \n"
    for event in all_events:
        result += f"\n{event['provider_icon']} {event['summary']}"
        if event.get('start'):
            result += f"\n   Time: {event['start']}"
        if event.get('location'):
            result += f"\n   Location: {event['location']}"
        if event.get('description'):
            result += f"\n   Description: {event['description']}"
        result += f"\n   ID: {event['id']}"
        result += "\n"
    return result

@tool
def delete_calendar_event(event_id: str) -> str:
    """
    Delete a calendar event from iCloud.
    Args:
        event_id: The event ID to delete
    Returns:
        Success or error message
    """
    calendars = get_all_calendars()
    if not calendars:
        return f"Error: iCloud calendar not configured."
    
    target_calendar = calendars[0]
    
    try:
        target_calendar.delete_event(event_id=event_id)
        icon = "🍎"
        return f"{icon} Event deleted from iCloud calendar."
    except Exception as e:
        return f"Error deleting event: {str(e)}"
            