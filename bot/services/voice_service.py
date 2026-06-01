import logging
import tempfile
from pathlib import Path

from openai import AsyncOpenAI
from telegram import Voice, Audio

from bot.config import settings

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe_voice(voice_file_bytes: bytes) -> str:
    """Transcribe voice message bytes (OGG/OGA) to text via Whisper API."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(voice_file_bytes)
        tmp_path = Path(tmp.name)

    try:
        with open(tmp_path, "rb") as audio_file:
            response = await _client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
            )
        return response.text.strip()
    finally:
        tmp_path.unlink(missing_ok=True)
