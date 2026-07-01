from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import settings
from src.services.whisper import transcribe_audio, _client as whisper_client


@pytest.fixture(autouse=True)
def reset_whisper_client():
    import src.services.whisper as w
    w._client = None
    yield
    w._client = None


@pytest.fixture
def mock_openai_client():
    mock_transcript = MagicMock()
    mock_transcript.text = "Termin am Freitag um 14 Uhr"

    mock_create = AsyncMock(return_value=mock_transcript)

    mock_transcriptions = MagicMock()
    mock_transcriptions.create = mock_create

    mock_audio = MagicMock()
    mock_audio.transcriptions = mock_transcriptions

    mock_client = MagicMock()
    mock_client.audio = mock_audio

    with patch("src.services.whisper.AsyncOpenAI", return_value=mock_client) as mock_constructor:
        yield mock_create, mock_constructor


class TestTranscribeAudio:
    async def test_returns_transcription_text(self, mock_openai_client):
        result = await transcribe_audio(b"\x00\x01\x02")
        assert result == "Termin am Freitag um 14 Uhr"

    async def test_passes_correct_model(self, mock_openai_client):
        await transcribe_audio(b"\x00\x01\x02")
        mock_create, _ = mock_openai_client
        mock_create.assert_awaited_once_with(
            model=settings.openrouter_stt_model,
            file=("audio.ogg", b"\x00\x01\x02"),
        )

    async def test_passes_custom_filename(self, mock_openai_client):
        await transcribe_audio(b"\x00\x01\x02", filename="voice.mp3")
        mock_create, _ = mock_openai_client
        mock_create.assert_awaited_once_with(
            model=settings.openrouter_stt_model,
            file=("voice.mp3", b"\x00\x01\x02"),
        )

    async def test_reuses_client_instance(self, mock_openai_client):
        await transcribe_audio(b"\x00")
        await transcribe_audio(b"\x01")
        mock_create, mock_constructor = mock_openai_client
        assert mock_create.await_count == 2
        mock_constructor.assert_called_once_with(
            api_key=settings.openrouter_api_key,
            base_url="https://api.openrouter.ai/v1",
        )