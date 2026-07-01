from pydantic_settings import BaseSettings
from typing import Optional
import json
import os


class Settings(BaseSettings):
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-4o"
    openrouter_extract_model: str = "openai/gpt-4o-mini"
    openrouter_stt_model: str = "openai/whisper-large-v3"
    google_service_account_file: str = "service-account.json"
    google_calendar_id: str
    bot_use_webhook: bool = False
    bot_webhook_url: Optional[str] = None
    bot_port: int = 8443
    timezone: str = "Europe/Berlin"

    @property
    def google_credentials(self) -> dict:
        path = self.google_service_account_file
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), "..", path)
        with open(path) as f:
            return json.load(f)

    @property
    def webhook_url(self) -> str:
        base = (self.bot_webhook_url or "").rstrip("/")
        return f"{base}/{self.telegram_bot_token}"

    @property
    def webhook_path(self) -> str:
        return self.telegram_bot_token

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()