import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import settings
from src.services.whisper import transcribe_audio


@pytest.fixture
def mock_httpx_post():
    with patch("src.services.whisper.httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Termin am Freitag um 14 Uhr"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        yield mock_client


class TestTranscribeAudio:
    async def test_returns_transcription_text(self, mock_httpx_post):
        result = await transcribe_audio(b"\x00\x01\x02")
        assert result == "Termin am Freitag um 14 Uhr"

    async def test_sends_base64_audio(self, mock_httpx_post):
        audio = b"\x00\x01\x02"
        await transcribe_audio(audio)
        call_kwargs = mock_httpx_post.post.call_args[1]
        assert call_kwargs["json"]["input_audio"]["data"] == base64.b64encode(audio).decode("ascii")
        assert call_kwargs["json"]["model"] == settings.openrouter_stt_model

    async def test_detects_format_from_filename(self, mock_httpx_post):
        await transcribe_audio(b"\x00\x01\x02", filename="voice.wav")
        call_kwargs = mock_httpx_post.post.call_args[1]
        assert call_kwargs["json"]["input_audio"]["format"] == "wav"

    async def test_defaults_to_ogg_format(self, mock_httpx_post):
        await transcribe_audio(b"\x00\x01\x02")
        call_kwargs = mock_httpx_post.post.call_args[1]
        assert call_kwargs["json"]["input_audio"]["format"] == "ogg"

    async def test_passes_correct_url_and_headers(self, mock_httpx_post):
        await transcribe_audio(b"\x00")
        call_kwargs = mock_httpx_post.post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == f"Bearer {settings.openrouter_api_key}"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"


class TestTranscribeAudioErrors:
    async def test_http_error_with_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error":"Invalid API key"}'
        mock_response.json.return_value = {"error": "Invalid API key"}
        http_exc = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)

        with patch("src.services.whisper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = http_exc
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError) as exc_info:
                await transcribe_audio(b"\x00\x01\x02")
            msg = str(exc_info.value)
            assert "HTTP 401" in msg
            assert "Invalid API key" in msg

    async def test_http_error_without_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = ""
        mock_response.json.side_effect = ValueError("no json")

        http_exc = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

        with patch("src.services.whisper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = http_exc
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError) as exc_info:
                await transcribe_audio(b"\x00\x01\x02")
            msg = str(exc_info.value)
            assert "HTTP 500" in msg

    async def test_network_error(self):
        net_exc = httpx.RequestError("Connection refused")

        with patch("src.services.whisper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = net_exc
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError) as exc_info:
                await transcribe_audio(b"\x00\x01\x02")
            msg = str(exc_info.value)
            assert "Netzwerkfehler" in msg

    async def test_missing_text_field(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid_key": "no text field"}
        mock_response.raise_for_status.return_value = None

        with patch("src.services.whisper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError) as exc_info:
                await transcribe_audio(b"\x00\x01\x02")
            msg = str(exc_info.value)
            assert "fehlendes Feld" in msg