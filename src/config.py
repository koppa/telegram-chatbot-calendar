from pydantic_settings import BaseSettings
from typing import Optional
import base64
import json


class Settings(BaseSettings):
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-4o"
    openrouter_extract_model: str = "openai/gpt-4o-mini"
    openai_api_key: str
    google_service_account_json: str
    google_calendar_id: str
    bot_webhook_url: str
    bot_port: int = 8443
    timezone: str = "Europe/Berlin"

    @property
    def google_credentials(self) -> dict:
        raw = self.google_service_account_json.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)

    @property
    def webhook_url(self) -> str:
        return f"{self.bot_webhook_url.rstrip('/')}/{self.telegram_bot_token}"

    @property
    def webhook_path(self) -> str:
        return self.telegram_bot_token

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
