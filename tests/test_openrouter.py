import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.openrouter import describe_image, extract_event
from src.models.event import CalendarEvent


FAKE_VISION_RESPONSE = {
    "choices": [{"message": {"content": "Ein Flyer mit einem Konzert am 15. Juli 2026 um 20 Uhr."}}]
}

FAKE_EXTRACT_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps({
                    "summary": "Zahnarzttermin",
                    "start_datetime": "2026-07-02T10:00:00",
                    "end_datetime": "2026-07-02T11:00:00",
                    "location": "Praxis Dr. Müller",
                    "description": "Jährliche Kontrolle",
                })
            }
        }
    ]
}

FAKE_EXTRACT_PARTIAL_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps({
                    "summary": "Meeting",
                    "start_datetime": None,
                    "duration_minutes": 60,
                })
            }
        }
    ]
}

FAKE_EXTRACT_EMPTY_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps({
                    "summary": None,
                    "start_datetime": None,
                })
            }
        }
    ]
}

FAKE_EXTRACT_ALL_DAY_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps({
                    "summary": "Ganztägiger Termin",
                    "start_datetime": "2026-07-02T00:00:00",
                    "is_all_day": True,
                })
            }
        }
    ]
}


@pytest.fixture
def mock_openrouter_request():
    with patch("src.services.openrouter._openrouter_request") as mock:
        yield mock


class TestDescribeImage:
    async def test_returns_description_text(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_VISION_RESPONSE
        result = await describe_image(b"\x00\x01\x02")
        assert "Konzert" in result
        assert "15. Juli" in result

    async def test_encodes_image_as_base64(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_VISION_RESPONSE
        await describe_image(b"test_bytes")
        body = mock_openrouter_request.call_args[0][0]
        msg = body["messages"][0]
        content = msg["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    async def test_uses_configured_model(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_VISION_RESPONSE
        with patch("src.services.openrouter.settings") as mock_settings:
            mock_settings.openrouter_model = "anthropic/claude-3.5-sonnet"
            await describe_image(b"\x00")
            body = mock_openrouter_request.call_args[0][0]
            assert body["model"] == "anthropic/claude-3.5-sonnet"


class TestExtractEvent:
    async def test_returns_calendar_event(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_RESPONSE
        result = await extract_event("Zahnarzt morgen um 10 Uhr", today="2026-07-01")
        assert isinstance(result, CalendarEvent)
        assert result.summary == "Zahnarzttermin"
        assert result.location == "Praxis Dr. Müller"

    async def test_includes_today_in_prompt(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_RESPONSE
        await extract_event("Termin morgen", today="2026-07-01")
        body = mock_openrouter_request.call_args[0][0]
        user_msg = body["messages"][1]["content"]
        assert "2026-07-01" in user_msg

    async def test_includes_context_in_prompt(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_RESPONSE
        await extract_event("10 Uhr", context="Titel: Meeting", today="2026-07-01")
        body = mock_openrouter_request.call_args[0][0]
        user_msg = body["messages"][1]["content"]
        assert "Previous context:" in user_msg
        assert "Titel: Meeting" in user_msg

    async def test_returns_none_when_both_fields_missing(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_EMPTY_RESPONSE
        result = await extract_event("irgendwas", today="2026-07-01")
        assert result is None

    async def test_handles_partial_data(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_PARTIAL_RESPONSE
        result = await extract_event("Meeting", today="2026-07-01")
        assert result is not None
        assert result.summary == "Meeting"
        assert result.start_datetime is None
        assert result.duration_minutes == 60

    async def test_uses_json_response_format(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_RESPONSE
        await extract_event("test", today="2026-07-01")
        body = mock_openrouter_request.call_args[0][0]
        assert body["response_format"] == {"type": "json_object"}

    async def test_parses_all_day_event(self, mock_openrouter_request):
        mock_openrouter_request.return_value = FAKE_EXTRACT_ALL_DAY_RESPONSE
        result = await extract_event("Ganztägiger Termin morgen", today="2026-07-01")
        assert result is not None
        assert result.summary == "Ganztägiger Termin"
        assert result.is_all_day is True
        assert result.start_datetime is not None
