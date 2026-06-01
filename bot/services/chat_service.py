import uuid
import logging
from datetime import datetime, timedelta, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Fact, Message, User
from bot.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — AstraCompanion, персональный AI-ассистент в Telegram с долговременной памятью. "
    "Ты общаешься как близкий товарищ — по-дружески, без официоза, на ты. "
    "У тебя ЕСТЬ долговременная память — ты хранишь факты о пользователе между разговорами. "
    "Если ниже в разделе [Воспоминания] есть информация о пользователе — ОБЯЗАТЕЛЬНО используй её в ответе. "
    "Никогда не говори, что ты не помнишь или не хранишь данные, если воспоминания присутствуют. "
    "Отвечай кратко и по делу, если пользователь не просит подробного ответа. "
    "НИКОГДА не используй Markdown-разметку: без звёздочек, без **, без __, без ```. "
    "Пиши простым текстом без форматирования. "
    "Отвечай на том языке, на котором пишет пользователь."
)


MEMORY_CONTEXT_HEADER = "\n\n[Воспоминания о пользователе — используй для персонализации ответа]:\n"


class ChatService:
    """Manages AI dialog with short-term session memory and long-term recall."""

    def __init__(self, session: AsyncSession, chroma=None) -> None:
        self.session = session
        self.chroma = chroma
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )

    async def get_response(self, user: User, text: str, force_new_session: bool = False) -> str:
        """Process user message and return AI response."""
        if force_new_session:
            session_id = uuid.uuid4()
        else:
            session_id = await self._get_or_create_session_id(user.id)

        # Save user message
        user_msg = Message(
            user_id=user.id,
            role="user",
            content=text,
            session_id=session_id,
        )
        self.session.add(user_msg)
        await self.session.flush()

        # Build context from session history + long-term memory
        messages = await self._build_context(user.id, session_id, text)

        # Call AI
        ai_response = await self._llm.ainvoke(messages)
        response_text = ai_response.content

        # Save assistant message
        assistant_msg = Message(
            user_id=user.id,
            role="assistant",
            content=response_text,
            session_id=session_id,
            tokens_used=ai_response.usage_metadata.get("total_tokens") if ai_response.usage_metadata else None,
        )
        self.session.add(assistant_msg)
        await self.session.commit()

        return response_text

    async def _get_or_create_session_id(self, user_id: int) -> uuid.UUID:
        """Get current session ID or create a new one if timed out."""
        timeout = datetime.utcnow() - timedelta(minutes=settings.session_timeout_minutes)

        result = await self.session.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .where(Message.created_at > timeout)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = result.scalar_one_or_none()

        if last_msg and last_msg.session_id:
            return last_msg.session_id

        return uuid.uuid4()

    async def _build_context(self, user_id: int, session_id: uuid.UUID, current_text: str) -> list:
        """Build message list for AI from session history + long-term memory."""
        result = await self.session.execute(
            select(Message)
            .where(Message.user_id == user_id, Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(settings.max_context_messages)
        )
        db_messages = result.scalars().all()

        # Build system prompt with memories
        system_content = SYSTEM_PROMPT
        memories = await self._recall_memories(user_id, current_text)
        if memories:
            system_content += MEMORY_CONTEXT_HEADER + memories

        messages = [SystemMessage(content=system_content)]

        for msg in db_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        return messages

    async def _recall_memories(self, user_id: int, query_text: str) -> str:
        """Build long-term memory context from stored facts and semantic search."""
        parts = []

        # Always include all user facts from PostgreSQL — they are always relevant
        try:
            result = await self.session.execute(
                select(Fact).where(Fact.user_id == user_id)
            )
            facts = result.scalars().all()
            for fact in facts:
                parts.append(f"- {fact.key}: {fact.value}")
        except Exception as e:
            logger.warning("Failed to load facts from DB: %s", e)

        # Semantic search for relevant notes/messages via ChromaDB
        if self.chroma:
            try:
                embedding = await get_embedding(query_text)
                for data_type in ("notes", "messages"):
                    try:
                        results = self.chroma.query(
                            user_id=user_id, data_type=data_type,
                            query_embedding=embedding, n_results=3,
                        )
                        if results and results.get("documents") and results["documents"][0]:
                            distances = results.get("distances", [[]])[0]
                            for i, doc in enumerate(results["documents"][0]):
                                score = 1 - distances[i] if i < len(distances) else 0
                                if score > 0.3:
                                    parts.append(f"- {doc}")
                    except Exception as e:
                        logger.debug("Recall from %s failed (may be empty): %s", data_type, e)
            except Exception as e:
                logger.warning("Failed to get embedding for memory recall: %s", e)

        return "\n".join(parts)
