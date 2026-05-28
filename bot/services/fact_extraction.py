import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Fact
from bot.database.chromadb_client import ChromaDBClient
from bot.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Ты — система извлечения фактов. Проанализируй сообщение пользователя и извлеки из него факты о пользователе.

Правила:
- Извлекай только явно упомянутые факты (имя, профессия, навыки, предпочтения, цели, хобби и т.д.)
- НЕ выдумывай факты, которых нет в тексте
- Если фактов нет — верни пустой список

Верни JSON-массив объектов. Каждый объект:
{
  "category": "personal_info" | "preference" | "skill" | "goal" | "hobby" | "other",
  "key": "краткий ключ на русском (например: имя, профессия, любимый_язык)",
  "value": "значение факта",
  "confidence": 0.0-1.0
}

Если фактов нет, верни: []

Отвечай ТОЛЬКО JSON-массивом, без пояснений."""


class FactExtractionService:
    """Extracts and stores user facts from conversation messages."""

    def __init__(self, session: AsyncSession, chroma: ChromaDBClient) -> None:
        self.session = session
        self.chroma = chroma
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,
        )

    async def extract_and_save(self, user_id: int, text: str, message_id: int | None = None) -> list[Fact]:
        """Extract facts from user text and save new/updated facts."""
        raw_facts = await self._extract_facts(text)
        if not raw_facts:
            return []

        saved = []
        for fact_data in raw_facts:
            fact = await self._upsert_fact(user_id, fact_data, message_id)
            if fact:
                saved.append(fact)

        if saved:
            await self.session.commit()

        return saved

    async def _extract_facts(self, text: str) -> list[dict]:
        """Use AI to extract facts from text."""
        messages = [
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=text),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            content = response.content.strip()

            # Strip markdown code block if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            facts = json.loads(content)
            if not isinstance(facts, list):
                return []
            return facts
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to extract facts: %s", e)
            return []

    async def _upsert_fact(self, user_id: int, fact_data: dict, message_id: int | None) -> Fact | None:
        """Insert new fact or update existing one (deduplication by key)."""
        category = fact_data.get("category", "other")
        key = fact_data.get("key", "")
        value = fact_data.get("value", "")
        confidence = fact_data.get("confidence", 1.0)

        if not key or not value:
            return None

        # Check for existing fact with same key
        result = await self.session.execute(
            select(Fact).where(Fact.user_id == user_id, Fact.key == key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.category = category
            existing.confidence = confidence
            if message_id:
                existing.source_message_id = message_id

            # Update vector
            if existing.chromadb_id:
                try:
                    embedding = await get_embedding(f"{key}: {value}")
                    self.chroma.update(
                        user_id=user_id,
                        data_type="facts",
                        doc_id=existing.chromadb_id,
                        text=f"{key}: {value}",
                        embedding=embedding,
                        metadata={"fact_id": existing.id, "category": category, "key": key},
                    )
                except Exception as e:
                    logger.warning("Failed to update fact vector: %s", e)

            return existing

        # Create new fact
        fact = Fact(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source_message_id=message_id,
        )
        self.session.add(fact)
        await self.session.flush()

        # Save vector
        try:
            chromadb_id = f"fact_{fact.id}"
            embedding = await get_embedding(f"{key}: {value}")
            self.chroma.add(
                user_id=user_id,
                data_type="facts",
                doc_id=chromadb_id,
                text=f"{key}: {value}",
                embedding=embedding,
                metadata={"fact_id": fact.id, "category": category, "key": key},
            )
            fact.chromadb_id = chromadb_id
        except Exception as e:
            logger.warning("Failed to save fact vector: %s", e)

        return fact

    async def get_user_facts(self, user_id: int) -> list[Fact]:
        """Get all facts for a user."""
        result = await self.session.execute(
            select(Fact).where(Fact.user_id == user_id).order_by(Fact.category, Fact.key)
        )
        return list(result.scalars().all())

    async def delete_fact(self, user_id: int, fact_id: int) -> bool:
        """Delete a specific fact."""
        result = await self.session.execute(
            select(Fact).where(Fact.user_id == user_id, Fact.id == fact_id)
        )
        fact = result.scalar_one_or_none()
        if not fact:
            return False

        if fact.chromadb_id:
            try:
                self.chroma.delete(user_id, "facts", [fact.chromadb_id])
            except Exception as e:
                logger.warning("Failed to delete fact vector: %s", e)

        await self.session.delete(fact)
        await self.session.commit()
        return True

    async def delete_all_facts(self, user_id: int) -> int:
        """Delete all facts for a user. Returns count of deleted facts."""
        facts = await self.get_user_facts(user_id)
        if not facts:
            return 0

        chroma_ids = [f.chromadb_id for f in facts if f.chromadb_id]
        if chroma_ids:
            try:
                self.chroma.delete(user_id, "facts", chroma_ids)
            except Exception as e:
                logger.warning("Failed to delete fact vectors: %s", e)

        count = len(facts)
        for fact in facts:
            await self.session.delete(fact)
        await self.session.commit()
        return count
