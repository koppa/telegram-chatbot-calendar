import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_CREDENTIALS = {
    "type": "service_account",
    "project_id": "test",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
    "client_email": "bot@test.iam.gserviceaccount.com",
    "client_id": "123",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}

# Write test credentials file next to this conftest
_creds_path = os.path.join(os.path.dirname(__file__), "test-service-account.json")
with open(_creds_path, "w") as f:
    json.dump(TEST_CREDENTIALS, f)

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:TESTTOKEN")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_FILE", _creds_path)
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@group.calendar.google.com")
os.environ.setdefault("BOT_WEBHOOK_URL", "https://example.com")
# Pin allowlist so tests are deterministic regardless of the real .env
os.environ["ALLOWED_USER_IDS"] = "[]"
