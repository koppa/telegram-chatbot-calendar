import logging
import base64
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

AUDIO_FORMATS = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".flac": "flac",
    ".m4a": "m4a",
    ".ogg": "ogg",
    ".webm": "webm",
    ".aac": "aac",
    ".oga": "ogg",
    ".opus": "ogg",
}


def _get_format(filename: str) -> str:
    _, ext = filename.rsplit(".", 1)
    return AUDIO_FORMATS.get("." + ext.lower(), "ogg")


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    fmt = _get_format(filename)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input_audio": {
                        "data": audio_b64,
                        "format": fmt,
                    },
                    "model": settings.openrouter_stt_model,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["text"]
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500] if e.response.text else "(no body)"
            logger.warning(
                "STT API HTTP error %s: %s",
                e.response.status_code,
                detail,
            )
            raise RuntimeError(
                f"STT API error (HTTP {e.response.status_code}): {detail}"
            ) from e
        except httpx.RequestError as e:
            logger.warning("STT API network error: %s", e)
            raise RuntimeError(
                f"Netzwerkfehler beim STT-API-Aufruf: {e}"
            ) from e
        except KeyError as e:
            logger.warning("STT API missing field in response: %s", e)
            raise RuntimeError(
                f"Unerwartete STT-API-Antwort (fehlendes Feld: {e})"
            ) from e
