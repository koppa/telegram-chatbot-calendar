import json
import os
from typing import Annotated, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-4o"
    openrouter_extract_model: str = "openai/gpt-4o-mini"
    openrouter_stt_model: str = "openai/whisper-large-v3"
    google_service_account_file: str = "service-account.json"
    google_calendar_id: str
    bot_port: int = 8443
    timezone: str = "Europe/Berlin"
    # Telegram user IDs allowed to use the bot. Empty list = allow everyone.
    # Accepts JSON list ("[123, 456]"), comma-separated ("123,456") or single ID ("123").
    allowed_user_ids: Annotated[list[int], NoDecode] = []

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_allowed_user_ids(cls, value):
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        "ALLOWED_USER_IDS must be a JSON list like [123, 456]"
                    ) from e
            try:
                return [int(part.strip()) for part in text.split(",") if part.strip()]
            except ValueError as e:
                raise ValueError(
                    "ALLOWED_USER_IDS must be a JSON list like [123, 456], "
                    "a comma-separated list like 123,456, or a single user ID"
                ) from e
        return value

    @property
    def google_credentials(self) -> dict:
        path = self.google_service_account_file
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), "..", path)
        with open(path) as f:
            return json.load(f)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()