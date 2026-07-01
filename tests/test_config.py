import base64
import json

import pytest

from src.config import Settings


SAMPLE_CREDENTIALS = {
    "type": "service_account",
    "project_id": "test-project",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "123456",
}


def minimal_settings(**overrides) -> Settings:
    defaults = {
        "telegram_bot_token": "123:ABC",
        "openrouter_api_key": "sk-or-v1-test",
        "openai_api_key": "sk-test",
        "google_service_account_json": json.dumps(SAMPLE_CREDENTIALS),
        "google_calendar_id": "test@group.calendar.google.com",
        "bot_webhook_url": "https://example.com",
        "bot_port": 8443,
        "timezone": "Europe/Berlin",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSettings:
    def test_webhook_url_combines_base_and_token(self):
        s = minimal_settings()
        assert s.webhook_url == "https://example.com/123:ABC"

    def test_webhook_url_strips_trailing_slash(self):
        s = minimal_settings(bot_webhook_url="https://example.com/")
        assert s.webhook_url == "https://example.com/123:ABC"

    def test_webhook_path_is_token(self):
        s = minimal_settings()
        assert s.webhook_path == "123:ABC"

    def test_google_credentials_from_raw_json(self):
        s = minimal_settings()
        creds = s.google_credentials
        assert creds["client_email"] == "test@test-project.iam.gserviceaccount.com"

    def test_google_credentials_from_base64(self):
        encoded = base64.b64encode(json.dumps(SAMPLE_CREDENTIALS).encode()).decode()
        s = minimal_settings(google_service_account_json=encoded)
        creds = s.google_credentials
        assert creds["client_email"] == "test@test-project.iam.gserviceaccount.com"

    def test_google_credentials_with_whitespace(self):
        s = minimal_settings(google_service_account_json="  " + json.dumps(SAMPLE_CREDENTIALS) + "  ")
        creds = s.google_credentials
        assert creds["client_email"] == "test@test-project.iam.gserviceaccount.com"

    def test_default_port(self):
        s = minimal_settings()
        assert s.bot_port == 8443

    def test_custom_port(self):
        s = minimal_settings(bot_port=9090)
        assert s.bot_port == 9090

    def test_default_timezone(self):
        s = minimal_settings()
        assert s.timezone == "Europe/Berlin"

    def test_custom_timezone(self):
        s = minimal_settings(timezone="America/New_York")
        assert s.timezone == "America/New_York"
