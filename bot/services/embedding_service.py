from openai import AsyncOpenAI

from bot.config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector for a text string."""
    response = await _client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding
