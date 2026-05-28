import uuid
import logging
from datetime import datetime, timedelta, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Message, User

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — AstraCompanion, персональный AI-ассистент в Telegram. "
    "Ты дружелюбный, полезный и внимательный. "
    "Ты помнишь контекст текущего разговора. "
    "Отвечай кратко и по делу, если пользователь не просит подробного ответа. "
    "Отвечай на том языке, на котором пишет пользователь."
)


class ChatService:
    """Manages AI dialog with short-term session memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
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

        # Build context from session history
        messages = await self._build_context(user.id, session_id)

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
        timeout = datetime.now(timezone.utc) - timedelta(minutes=settings.session_timeout_minutes)

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

    async def _build_context(self, user_id: int, session_id: uuid.UUID) -> list:
        """Build message list for AI from session history."""
        result = await self.session.execute(
            select(Message)
            .where(Message.user_id == user_id, Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(settings.max_context_messages)
        )
        db_messages = result.scalars().all()

        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        for msg in db_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        return messages
