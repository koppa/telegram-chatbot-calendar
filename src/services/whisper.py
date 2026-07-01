from openai import AsyncOpenAI

from src.config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://api.openrouter.ai/v1",
        )
    return _client


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    client = _get_client()
    transcript = await client.audio.transcriptions.create(
        model=settings.openrouter_stt_model,
        file=(filename, audio_bytes),
    )
    return transcript.text
