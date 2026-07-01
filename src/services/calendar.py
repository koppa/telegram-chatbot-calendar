from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from src.config import settings
from src.models.event import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

DEFAULT_DURATION = 30


def _localize(dt: datetime) -> datetime:
    tz = ZoneInfo(settings.timezone)
    if dt.tzinfo is not None:
        return dt.astimezone(tz)
    return dt.replace(tzinfo=tz)


_service = None


def _get_service():
    global _service
    if _service is None:
        creds = Credentials.from_service_account_info(
            settings.google_credentials, scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=creds)
    return _service


async def create_event(event: CalendarEvent) -> str:
    service = _get_service()

    start = _localize(event.start_datetime)
    body = {
        "summary": event.summary,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": settings.timezone,
        },
    }

    if event.end_datetime:
        end = _localize(event.end_datetime)
    elif event.duration_minutes:
        end = start + timedelta(minutes=event.duration_minutes)
    else:
        end = start + timedelta(minutes=DEFAULT_DURATION)

    body["end"] = {
        "dateTime": end.isoformat(),
        "timeZone": settings.timezone,
    }

    if event.location:
        body["location"] = event.location
    if event.description:
        body["description"] = event.description

    created = (
        service.events()
        .insert(calendarId=settings.google_calendar_id, body=body)
        .execute()
    )
    return created.get("htmlLink", "")
