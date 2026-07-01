import json
from datetime import date, datetime
from typing import Optional
import aiohttp
import base64

from src.config import settings
from src.models.event import CalendarEvent


SYSTEM_EXTRACT_PROMPT = """You are a calendar event parser. Extract event information from the user's message.
Return a JSON object with these fields:
- "summary": event title (string, required). If no clear title is given, set this to null.
- "start_datetime": ISO 8601 datetime string (required). Infer the date from context like "morgen" (tomorrow), "übermorgen", "nächste Woche", weekday names, etc. Today's date will be provided. If the date or time cannot be determined, set this to null.
- "end_datetime": ISO 8601 datetime string (optional). Infer from words like "bis", "until", duration like "1 Stunde".
- "duration_minutes": integer (optional, used if end_datetime not specified)
- "location": string (optional)
- "description": string (optional)

Return ONLY valid JSON, no other text."""

VISION_PROMPT = "Describe this image. Extract all visible text and any event-related information (dates, times, locations, names)."


async def _openrouter_request(body: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data


async def describe_image(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{encoded}"
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 1000,
    }
    data = await _openrouter_request(body)
    return data["choices"][0]["message"]["content"]


async def extract_event(text: str, *, context: str = "", today: str = "") -> Optional[CalendarEvent]:
    user_prompt = text
    if context:
        user_prompt = f"Previous context: {context}\n\nUser message: {text}"
    if today:
        user_prompt = f"Today's date: {today}\n\n{user_prompt}"

    body = {
        "model": settings.openrouter_extract_model,
        "messages": [
            {"role": "system", "content": SYSTEM_EXTRACT_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    data = await _openrouter_request(body)
    raw = data["choices"][0]["message"]["content"]
    parsed = json.loads(raw)

    if not parsed.get("summary") and not parsed.get("start_datetime"):
        return None

    start_dt = None
    end_dt = None
    if parsed.get("start_datetime"):
        try:
            start_dt = datetime.fromisoformat(parsed["start_datetime"])
        except (ValueError, TypeError):
            pass
    if parsed.get("end_datetime"):
        try:
            end_dt = datetime.fromisoformat(parsed["end_datetime"])
        except (ValueError, TypeError):
            pass

    return CalendarEvent(
        summary=parsed.get("summary") or "",
        start_datetime=start_dt,
        end_datetime=end_dt,
        duration_minutes=parsed.get("duration_minutes"),
        location=parsed.get("location"),
        description=parsed.get("description"),
    )
