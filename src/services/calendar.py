from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from src.config import settings
from src.models.event import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


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

    tz = settings.timezone
    body = {
        "summary": event.summary,
        "start": {
            "dateTime": event.start_datetime.isoformat(),
            "timeZone": tz,
        },
    }

    if event.end_datetime:
        body["end"] = {
            "dateTime": event.end_datetime.isoformat(),
            "timeZone": tz,
        }
    elif event.duration_minutes:
        from datetime import timedelta
        end = event.start_datetime + timedelta(minutes=event.duration_minutes)
        body["end"] = {
            "dateTime": end.isoformat(),
            "timeZone": tz,
        }
    else:
        body["end"] = body["start"]

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
