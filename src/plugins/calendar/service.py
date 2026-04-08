import logging
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
import pytz
from caldav import DAVClient
from icalendar import Calendar as iCalendar
from icalendar import Event as IEvent
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_CALDAV_TIMEOUT = 30
_MAX_RETRIES = 3


class CalendarService:
    def __init__(self, username: str, password: str, agent_name: str = "personal"):
        """
        Initialize CalDAV calendar service for iCloud only.

        Args:
            username: iCloud email/Apple ID
            password: App-specific password from appleid.apple.com
            agent_name: Agent name used as iCal CATEGORIES tag (e.g. "business", "personal")
        """
        self.provider = "icloud"
        self.agent_name = agent_name
        url = "https://caldav.icloud.com/"

        self._url = url
        self._username = username
        self._password = password
        self._connect()

    def _connect(self) -> None:
        """(Re)establish the CalDAV connection."""
        try:
            self.client = DAVClient(
                url=self._url,
                username=self._username,
                password=self._password,
                timeout=_CALDAV_TIMEOUT,
            )
            self.principal = self.client.principal()
            calendars = self.principal.calendars()
            self.calendar = None

            if not calendars:
                raise Exception("No calendars found")
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

    def _retry(self, fn, *args, **kwargs):
        """Call *fn* with reconnect-and-retry on timeout/connection errors."""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                is_retryable = "timed out" in str(e).lower() or "connection" in str(e).lower()
                if not is_retryable or attempt == _MAX_RETRIES:
                    raise
                wait = 2**attempt
                logger.warning(f"CalDAV attempt {attempt}/{_MAX_RETRIES} failed: {e}. Reconnecting in {wait}s...")
                time.sleep(wait)
                self._connect()

    def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: str | None = None,
        location: str | None = None,
        timezone: str = "America/New_York",
        reminder_minutes: int = 30,
    ) -> dict[str, Any]:
        try:
            cal = iCalendar()
            cal.add("prodid", "-//Personal Assistant Agent//EN")
            cal.add("version", "2.0")

            event = IEvent()

            tz = pytz.timezone(timezone)

            if start_time.tzinfo is None:
                start_time = tz.localize(start_time)
            if end_time.tzinfo is None:
                end_time = tz.localize(end_time)

            event.add("summary", summary)
            event.add("dtstart", start_time)
            event.add("dtend", end_time)
            event.add("uid", f"{datetime.now().timestamp()}@personal-assistant")
            event.add("dtstamp", datetime.now(pytz.utc))

            if description:
                event.add("description", description)
            if location:
                event.add("location", location)
            event.add("categories", [self.agent_name])

            if reminder_minutes > 0:
                from icalendar import Alarm

                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("trigger", timedelta(minutes=-reminder_minutes))
                alarm.add("description", f"Reminder: {summary}")
                event.add_component(alarm)
                second_alarm = Alarm()
                second_alarm.add("action", "DISPLAY")
                second_alarm.add("trigger", timedelta(days=-1))
                second_alarm.add("description", f"Reminder: {summary}")
                event.add_component(second_alarm)

            cal.add_component(event)

            ical_string = cal.to_ical().decode("utf-8")
            created_event = self._retry(self.calendar.save_event, ical_string)
            logger.info(f"Event created in {self.provider}: {summary}")

            return {
                "summary": summary,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "id": str(created_event.id),
                "provider": self.provider,
            }
        except Exception as e:
            logger.error(f"Error creating event in {self.provider}: {e}")
            raise

    def list_events(
        self,
        max_results: int = 10,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> list[dict[str, Any]]:
        try:
            if time_min is None:
                time_min = datetime.now()
            if time_max is None:
                time_max = time_min + timedelta(days=30)

            events = self._retry(
                self.calendar.date_search,
                start=time_min,
                end=time_max,
                expand=True,
            )
            results = []

            for event in events[:max_results]:
                vev = event.vobject_instance.vevent
                categories = None
                if hasattr(vev, "categories"):
                    cats = vev.categories.value
                    categories = list(cats) if isinstance(cats, list | tuple) else [str(cats)]
                results.append(
                    {
                        "summary": str(vev.summary.value),
                        "start": vev.dtstart.value.isoformat() if hasattr(vev, "dtstart") else None,
                        "end": vev.dtend.value.isoformat() if hasattr(vev, "dtend") else None,
                        "description": vev.description.value if hasattr(vev, "description") else None,
                        "location": vev.location.value if hasattr(vev, "location") else None,
                        "categories": categories,
                        "id": str(event.url),
                        "provider": self.provider,
                    }
                )

            logger.info(f"Retrieved {len(results)} events from {self.provider}")
            return results

        except Exception as e:
            logger.error(f"Error listing events from {self.provider}: {e}")
            return []

    def search_events(
        self,
        query: str,
        max_results: int = 10,
        time_min: datetime | None = None,
    ) -> list[dict[str, Any]]:
        try:
            if time_min is None:
                time_min = datetime.now()

            time_max = time_min + timedelta(days=365)

            events = self._retry(
                self.calendar.date_search,
                start=time_min,
                end=time_max,
                expand=True,
            )

            results = []
            for event in events:
                vev = event.vobject_instance.vevent
                summary = str(vev.summary.value) if hasattr(vev, "summary") else ""
                description = str(vev.description.value) if hasattr(vev, "description") else ""

                if query.lower() in summary.lower() or query.lower() in description.lower():
                    categories = None
                    if hasattr(vev, "categories"):
                        cats = vev.categories.value
                        categories = list(cats) if isinstance(cats, list | tuple) else [str(cats)]
                    results.append(
                        {
                            "summary": summary,
                            "start": vev.dtstart.value.isoformat() if hasattr(vev, "dtstart") else None,
                            "end": vev.dtend.value.isoformat() if hasattr(vev, "dtend") else None,
                            "description": description,
                            "location": vev.location.value if hasattr(vev, "location") else None,
                            "categories": categories,
                            "id": str(event.url),
                            "provider": self.provider,
                        }
                    )

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
            event = self._retry(self.calendar.event_by_url, event_id)
            self._retry(event.delete)
            logger.info(f"Event deleted from {self.provider}: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting event from {self.provider}: {e}")
            raise


def _make_tools(get_service: callable) -> list:
    """Build @tool functions closed over a service getter."""

    @tool
    def create_calendar_event(
        summary: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        description: str = "",
        location: str = "",
        timezone: str = "America/New_York",
    ) -> str:
        """
        Create a calendar event in iCloud calendar.
        Args:
            summary: Event title
            date: Date in natural language or absolute format (e.g., "saturday", "tomorrow", "jan 24", "2026-01-24")
            time: Time of the event (e.g., "2pm", "14:00", "3:30pm")
            duration_minutes: Duration of event in minutes (default: 60)
            description: Event description
            location: Event location
            timezone: Timezone (default: America/New_York)
        Returns:
            Success message
        """
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        parsed_date = dateparser.parse(
            date,
            settings={
                "TIMEZONE": timezone,
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": now.replace(tzinfo=None),
            },
        )

        if not parsed_date:
            return f"Error: could not parse date'{date}'"

        parsed_time = dateparser.parse(time)
        if not parsed_time:
            return f"Error: could not parse time'{time}'"

        start_dt = parsed_date.replace(
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=0,
            microsecond=0,
        )

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)

        end_dt = start_dt + timedelta(minutes=duration_minutes)

        calendar = get_service()
        if not calendar:
            return "Error: Calendar service not available."

        try:
            calendar.create_event(
                summary=summary,
                start_time=start_dt,
                end_time=end_dt,
                description=description,
                location=location,
                timezone=timezone,
            )
            return f"Event '{summary}' created in iCloud calendar"
        except Exception as e:
            return f"Error creating event: {e!s}"

    @tool
    def list_calendar_events(max_results: int = 10) -> str:
        """
        List upcoming events from iCloud calendar.
        Args:
            max_results: Maximum number of events (default: 10)
        Returns:
            Formatted list of events
        """
        calendar = get_service()
        if not calendar:
            return "No calendar configured"

        try:
            events = calendar.list_events(max_results=max_results)
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            return f"Error listing events: {e}"

        if not events:
            return "No upcoming events found."

        events.sort(key=lambda e: e.get("start", ""))
        result = "Upcoming events: \n"
        for event in events:
            result += f"\n   ID: {event['id']}"
            result += f"\n {event['summary']}"
            if event.get("start"):
                result += f"\n   Time: {event['start']}"
            if event.get("location"):
                result += f"\n   Location: {event['location']}"
            if event.get("description"):
                result += f"\n   Description: {event['description']}"
            result += "\n"
        return result

    @tool
    def search_calendar_events(query: str, max_results: int = 10) -> str:
        """
        Search for events in iCloud calendar.
        Args:
            query: Search query to match against event titles and descriptions
            max_results: Maximum number of results (default: 10)
        Returns:
            Formatted list of matching events
        """
        calendar = get_service()
        if not calendar:
            return "No calendar configured"

        try:
            events = calendar.search_events(query=query, max_results=max_results)
        except Exception as e:
            logger.error(f"Error searching events: {e}")
            return f"Error searching events: {e}"

        if not events:
            return f"No events found matching '{query}'."

        events.sort(key=lambda e: e.get("start", ""))
        result = f"Events matching '{query}': \n"
        for event in events:
            result += f"\n {event['summary']}"
            if event.get("start"):
                result += f"\n   Time: {event['start']}"
            if event.get("location"):
                result += f"\n   Location: {event['location']}"
            if event.get("description"):
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
        calendar = get_service()
        if not calendar:
            return "Error: Calendar not configured."

        try:
            calendar.delete_event(event_id=event_id)
            return "Event deleted from iCloud calendar."
        except Exception as e:
            return f"Error deleting event: {e!s}"

    return [
        create_calendar_event,
        search_calendar_events,
        list_calendar_events,
        delete_calendar_event,
    ]
