import json
import logging
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Reminder

logger = logging.getLogger(__name__)

DATE_PARSE_PROMPT = """Ты парсишь время из текста пользователя. Текущее время (UTC): {now}

Верни JSON:
{{
  "trigger_at": "YYYY-MM-DD HH:MM" (в UTC),
  "text": "текст напоминания без временной части",
  "is_recurring": false,
  "recurrence_rule": null
}}

Если указано "каждый день в X" или "каждый понедельник" — is_recurring=true, recurrence_rule="cron выражение".
Если не удаётся определить время — верни null в trigger_at.
Отвечай ТОЛЬКО JSON."""


class ReminderService:
    """CRUD operations for reminders with natural language time parsing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,
        )

    async def create_reminder(self, user_id: int, text: str) -> Reminder | None:
        """Create a reminder by parsing natural language time."""
        parsed = await self._parse_reminder(text)
        if not parsed or not parsed.get("trigger_at"):
            return None

        try:
            trigger_at = datetime.strptime(parsed["trigger_at"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        reminder = Reminder(
            user_id=user_id,
            text=parsed.get("text", text),
            trigger_at=trigger_at,
            is_recurring=parsed.get("is_recurring", False),
            recurrence_rule=parsed.get("recurrence_rule"),
        )
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def list_reminders(self, user_id: int) -> list[Reminder]:
        """List all active reminders for a user."""
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.status == "active")
            .order_by(Reminder.trigger_at.asc())
        )
        return list(result.scalars().all())

    async def get_due_reminders(self) -> list[Reminder]:
        """Get all reminders that are due (trigger_at <= now)."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.status == "active", Reminder.trigger_at <= now)
        )
        return list(result.scalars().all())

    async def mark_triggered(self, reminder_id: int) -> None:
        """Mark a reminder as triggered."""
        result = await self.session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.status = "triggered"
            await self.session.commit()

    async def snooze(self, reminder_id: int, new_trigger_at: datetime) -> Reminder | None:
        """Snooze a reminder to a new time."""
        result = await self.session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if not reminder:
            return None

        reminder.trigger_at = new_trigger_at
        reminder.status = "active"
        await self.session.commit()
        return reminder

    async def delete_reminder(self, user_id: int, reminder_id: int) -> bool:
        """Delete a reminder."""
        result = await self.session.execute(
            select(Reminder).where(Reminder.user_id == user_id, Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if not reminder:
            return False

        await self.session.delete(reminder)
        await self.session.commit()
        return True

    async def _parse_reminder(self, text: str) -> dict | None:
        """Use AI to parse time and text from natural language."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        try:
            messages = [
                SystemMessage(content=DATE_PARSE_PROMPT.format(now=now)),
                HumanMessage(content=text),
            ]
            response = await self._llm.ainvoke(messages)
            content = response.content.strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            return json.loads(content)
        except Exception as e:
            logger.warning("Failed to parse reminder: %s", e)
            return None
