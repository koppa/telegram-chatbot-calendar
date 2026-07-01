import json
from datetime import datetime, date
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.event import CalendarEvent


SAMPLE_EVENT = CalendarEvent(
    summary="Zahnarzttermin",
    start_datetime=datetime(2026, 7, 2, 10, 0),
    end_datetime=datetime(2026, 7, 2, 11, 0),
    location="Praxis Dr. Müller",
    description="Jährliche Kontrolle",
)


class TestCalendarEvent:
    def test_minimal_event(self):
        event = CalendarEvent(
            summary="Meeting",
            start_datetime=datetime(2026, 7, 2, 14, 0),
        )
        assert event.summary == "Meeting"
        assert event.end_datetime is None
        assert event.duration_minutes is None

    def test_full_event(self):
        event = SAMPLE_EVENT
        assert event.duration_minutes is None
        assert event.location == "Praxis Dr. Müller"
        assert event.description == "Jährliche Kontrolle"

    def test_event_with_duration(self):
        event = CalendarEvent(
            summary="Call",
            start_datetime=datetime(2026, 7, 2, 15, 0),
            duration_minutes=30,
        )
        assert event.duration_minutes == 30

    def test_model_dump_roundtrip(self):
        data = SAMPLE_EVENT.model_dump()
        restored = CalendarEvent.model_validate(data)
        assert restored == SAMPLE_EVENT

    def test_model_dump_excludes_none(self):
        event = CalendarEvent(summary="Test", start_datetime=datetime(2026, 7, 2, 12, 0))
        data = event.model_dump(exclude_none=True)
        assert "end_datetime" not in data
        assert "duration_minutes" not in data
        assert "location" not in data

    def test_all_day_event(self):
        event = CalendarEvent(
            summary="Ganztägig",
            start_datetime=datetime(2026, 7, 2),
            is_all_day=True,
        )
        assert event.is_all_day is True
        assert event.start_datetime.hour == 0
        assert event.start_datetime.minute == 0
