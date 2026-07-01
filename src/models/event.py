from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CalendarEvent(BaseModel):
    summary: str
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
