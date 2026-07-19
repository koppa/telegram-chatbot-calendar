# Telegram → Google Calendar Bot

A Python bot that receives Telegram messages (text, photo, voice/audio), extracts structured event data via LLM, and creates events in Google Calendar.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.13+ |
| Telegram | [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21+ (async) |
| Image Analysis | OpenRouter Vision API (`openai/gpt-4o`) |
| Audio Transcription | OpenRouter Whisper API (`openai/whisper-large-v3`) |
| LLM Extraction | OpenRouter text model with JSON output |
| Calendar API | Google Calendar API v3 (Service Account) |
| Container | Docker + docker-compose |

## Data Flow

```
Telegram User
  │
  ├─ Text ──────────────────────┐
  ├─ Photo ──► OpenRouter Vision ──► text ──┤
  ├─ Voice ──► OpenRouter Whisper ────► text ──┤
  └─ Document (image) ──► OpenRouter Vision ──► text ──┤
                                                         │
                               LLM Structured Extraction ◄─┘
                                     │
                               Google Calendar API
                                     │
                      Success/Failure → Telegram
```

## Prerequisites

1. **Telegram Bot Token** – Create a bot via [@BotFather](https://t.me/BotFather)
2. **OpenRouter API Key** – Sign up at [openrouter.ai](https://openrouter.ai)
3. **Google Cloud Project + Service Account**:
   - Create a project in the [Google Cloud Console](https://console.cloud.google.com)
   - Enable the Google Calendar API
   - Create a service account, download the JSON key
   - Share your target Google Calendar with the service account email as editor

## Setup

```bash
# Clone the repository
cd telegram-calendar-bot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Fill in your tokens and keys in .env
```

### `.env` Configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `OPENROUTER_API_KEY` | API key from OpenRouter |
| `OPENROUTER_MODEL` | Vision model (default: `openai/gpt-4o`) |
| `OPENROUTER_EXTRACT_MODEL` | Extraction model (default: `openai/gpt-4o-mini`) |
| `OPENROUTER_STT_MODEL` | Speech-to-text model (default: `openai/whisper-large-v3`) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the service account JSON file |
| `GOOGLE_CALENDAR_ID` | Shared calendar ID |
| `BOT_PORT` | Port (default: 8443) |
| `TIMEZONE` | Timezone (default: `Europe/Berlin`) |
| `ALLOWED_USER_IDS` | Allowed Telegram user IDs: JSON list (`[123456]`), comma-separated (`123,456`) or single ID (empty = open to everyone) |

## Running

### Local (Polling)

```bash
source .venv/bin/activate
python -m src.main
```

### Docker

```bash
docker compose up --build
```

## Usage

Send the bot a message with event details:

- **Text**: `Dentist appointment tomorrow at 10 AM for 1 hour`
- **Photo**: Screenshot of a calendar entry or flyer
- **Voice message**: Dictated event details

The bot extracts the information and asks follow-up questions if details are missing. After confirmation, the event is created in your Google Calendar.

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Project Structure

```
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
├── src/
│   ├── config.py               # Environment variables (pydantic-settings)
│   ├── main.py                 # Entry point
│   ├── bot/
│   │   ├── handlers.py         # ConversationHandler + message handlers
│   │   └── states.py           # Dialog state constants
│   ├── services/
│   │   ├── openrouter.py       # OpenRouter Vision + LLM extraction
│   │   ├── whisper.py          # OpenRouter Whisper transcription
│   │   └── calendar.py         # Google Calendar API
│   └── models/
│       └── event.py            # CalendarEvent Pydantic model
└── tests/
    ├── conftest.py
    ├── test_calendar.py
    ├── test_config.py
    ├── test_event_model.py
    ├── test_openrouter.py
    └── test_whisper.py
```
