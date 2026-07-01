from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.services.calendar import create_event
from src.models.event import CalendarEvent


SAMPLE_EVENT = CalendarEvent(
    summary="Zahnarzttermin",
    start_datetime=datetime(2026, 7, 2, 10, 0),
    end_datetime=datetime(2026, 7, 2, 11, 0),
    location="Praxis Dr. Müller",
    description="Jährliche Kontrolle",
)


@pytest.fixture
def mock_service():
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"htmlLink": "https://calendar.google.com/event?eid=abc"})
    mock_insert.execute = mock_execute

    mock_events = MagicMock()
    mock_events.insert.return_value = mock_insert

    mock_service = MagicMock()
    mock_service.events.return_value = mock_events

    with patch("src.services.calendar._get_service", return_value=mock_service):
        yield mock_service


class TestCreateEvent:
    async def test_returns_html_link(self, mock_service):
        link = await create_event(SAMPLE_EVENT)
        assert link == "https://calendar.google.com/event?eid=abc"

    async def test_sends_correct_body_with_end_datetime(self, mock_service):
        await create_event(SAMPLE_EVENT)
        insert_call = mock_service.events.return_value.insert
        body = insert_call.call_args[1]["body"]
        assert body["summary"] == "Zahnarzttermin"
        assert body["start"]["timeZone"] == "Europe/Berlin"
        assert body["end"]["dateTime"] == "2026-07-02T11:00:00+02:00"
        assert body["location"] == "Praxis Dr. Müller"
        assert body["description"] == "Jährliche Kontrolle"

    async def test_uses_duration_when_no_end_datetime(self, mock_service):
        event = CalendarEvent(
            summary="Call",
            start_datetime=datetime(2026, 7, 2, 15, 0),
            duration_minutes=30,
        )
        await create_event(event)
        body = mock_service.events.return_value.insert.call_args[1]["body"]
        assert "2026-07-02T15:30:00" in body["end"]["dateTime"]

    async def test_defaults_to_30min_when_no_end_or_duration(self, mock_service):
        event = CalendarEvent(
            summary="Ganztägig",
            start_datetime=datetime(2026, 7, 2, 10, 0),
        )
        await create_event(event)
        body = mock_service.events.return_value.insert.call_args[1]["body"]
        assert body["end"]["dateTime"] == "2026-07-02T10:30:00+02:00"

    async def test_sends_correct_calendar_id(self, mock_service):
        await create_event(SAMPLE_EVENT)
        insert_call = mock_service.events.return_value.insert
        assert insert_call.call_args[1]["calendarId"] == "test@group.calendar.google.com"

    async def test_omits_optional_fields(self, mock_service):
        event = CalendarEvent(summary="Minimal", start_datetime=datetime(2026, 7, 2, 12, 0))
        await create_event(event)
        body = mock_service.events.return_value.insert.call_args[1]["body"]
        assert "location" not in body
        assert "description" not in body
