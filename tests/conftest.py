import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set env vars before any src.config import so module-level settings = Settings() works
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:TESTTOKEN")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    '{"type":"service_account","project_id":"test","private_key":"-----BEGIN PRIVATE KEY-----\\nMOCK\\n-----END PRIVATE KEY-----","client_email":"bot@test.iam.gserviceaccount.com","client_id":"123","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}',
)
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@group.calendar.google.com")
os.environ.setdefault("BOT_WEBHOOK_URL", "https://example.com")