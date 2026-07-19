import json
import os
import tempfile

import pytest
from pydantic import ValidationError

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
        "google_calendar_id": "test@group.calendar.google.com",
        "bot_port": 8443,
        "timezone": "Europe/Berlin",
    }
    defaults.update(overrides)
    if "google_service_account_file" not in overrides:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(SAMPLE_CREDENTIALS, tmp)
        tmp.close()
        defaults["google_service_account_file"] = tmp.name
    return Settings(**defaults)


class TestSettings:
    def test_google_credentials_from_file(self):
        s = minimal_settings()
        creds = s.google_credentials
        assert creds["client_email"] == "test@test-project.iam.gserviceaccount.com"
        assert creds["project_id"] == "test-project"

    def test_google_credentials_custom_path(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(
            {"client_email": "custom@project.iam.gserviceaccount.com", "project_id": "custom"},
            tmp,
        )
        tmp.close()
        s = minimal_settings(google_service_account_file=tmp.name)
        creds = s.google_credentials
        assert creds["client_email"] == "custom@project.iam.gserviceaccount.com"

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

    def test_allowed_user_ids_default_empty(self):
        s = minimal_settings()
        assert s.allowed_user_ids == []

    def test_allowed_user_ids_custom(self):
        s = minimal_settings(allowed_user_ids=[123, 456])
        assert s.allowed_user_ids == [123, 456]

    def test_allowed_user_ids_from_env(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "[123, 456]")
        s = minimal_settings()
        assert s.allowed_user_ids == [123, 456]

    def test_allowed_user_ids_bare_int(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "123456789")
        s = minimal_settings()
        assert s.allowed_user_ids == [123456789]

    def test_allowed_user_ids_comma_separated(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "123,456")
        s = minimal_settings()
        assert s.allowed_user_ids == [123, 456]

    def test_allowed_user_ids_comma_separated_with_spaces(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "123, 456, 789")
        s = minimal_settings()
        assert s.allowed_user_ids == [123, 456, 789]

    def test_allowed_user_ids_empty_string(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "")
        s = minimal_settings()
        assert s.allowed_user_ids == []

    def test_allowed_user_ids_whitespace(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "   ")
        s = minimal_settings()
        assert s.allowed_user_ids == []

    def test_allowed_user_ids_int_kwarg(self):
        s = minimal_settings(allowed_user_ids=123)
        assert s.allowed_user_ids == [123]

    def test_allowed_user_ids_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_USER_IDS", "abc")
        with pytest.raises(ValidationError):
            minimal_settings()
