import logging
from datetime import datetime

from notion_client import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Note, Task, Fact, Reminder, User

logger = logging.getLogger(__name__)


def _text(content: str, bold: bool = False, italic: bool = False, code: bool = False) -> dict:
    """Create a rich text element."""
    annotations = {}
    if bold:
        annotations["bold"] = True
    if italic:
        annotations["italic"] = True
    if code:
        annotations["code"] = True
    rt = {"type": "text", "text": {"content": content}}
    if annotations:
        rt["annotations"] = annotations
    return rt


def _heading(level: int, text: str) -> dict:
    """Create a heading block (1, 2, or 3)."""
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_text(text)]}}


def _paragraph(rich_texts: list[dict]) -> dict:
    """Create a paragraph block."""
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_texts}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _bulleted(rich_texts: list[dict]) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_texts}}


def _todo(text_parts: list[dict], checked: bool = False) -> dict:
    return {"object": "block", "type": "to_do", "to_do": {"rich_text": text_parts, "checked": checked}}


class NotionService:
    """Export user data to Notion as beautifully formatted pages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._notion = AsyncClient(auth=settings.notion_api_token)
        self._parent_page_id = settings.notion_parent_page_id

    async def export_all(self, user_id: int) -> str:
        """Export all user data to Notion. Updates existing page or creates new."""
        facts = await self._get_facts(user_id)
        notes = await self._get_notes(user_id)
        tasks = await self._get_tasks(user_id)
        reminders = await self._get_reminders(user_id)

        blocks = self._build_blocks(facts, notes, tasks, reminders)

        # Check if user already has an export page
        user = await self.session.execute(select(User).where(User.id == user_id))
        user = user.scalar_one()

        page_id = user.notion_export_page_id

        # Try to reuse existing page
        if page_id:
            try:
                await self._clear_page(page_id)
                now = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
                await self._notion.pages.update(
                    page_id=page_id,
                    properties={"title": {"title": [_text(f"AstraCompanion Export — {now}")]}},
                )
            except Exception:
                logger.info("Previous Notion page not found, creating new one")
                page_id = None

        # Create new page if needed
        if not page_id:
            now = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
            first_batch = blocks[:100]
            remaining_blocks = blocks[100:]

            page = await self._notion.pages.create(
                parent={"page_id": self._parent_page_id},
                properties={"title": {"title": [_text(f"AstraCompanion Export — {now}")]}},
                children=first_batch,
            )
            page_id = page["id"]

            while remaining_blocks:
                batch = remaining_blocks[:100]
                remaining_blocks = remaining_blocks[100:]
                await self._notion.blocks.children.append(block_id=page_id, children=batch)

            # Save page ID for future updates
            user.notion_export_page_id = page_id
            await self.session.commit()

            return page["url"]

        # Append blocks to cleared page
        remaining = blocks
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            await self._notion.blocks.children.append(block_id=page_id, children=batch)

        return f"https://www.notion.so/{page_id.replace('-', '')}"

    async def _clear_page(self, page_id: str) -> None:
        """Delete all blocks from an existing page."""
        children = await self._notion.blocks.children.list(block_id=page_id)
        for block in children.get("results", []):
            await self._notion.blocks.delete(block_id=block["id"])

    def _build_blocks(
        self,
        facts: list[Fact],
        notes: list[Note],
        tasks: list[Task],
        reminders: list[Reminder],
    ) -> list[dict]:
        """Build Notion blocks for all user data."""
        blocks = []

        # Profile / Facts
        if facts:
            blocks.append(_heading(1, "Профиль пользователя"))
            for f in facts:
                blocks.append(_bulleted([_text(f"{f.key}: ", bold=True), _text(f.value)]))
            blocks.append(_divider())

        # Notes
        blocks.append(_heading(1, "Заметки"))
        if notes:
            for n in notes:
                title = n.summary or "Без названия"
                blocks.append(_heading(3, title))

                meta_parts = []
                if n.created_at:
                    meta_parts.append(_text(n.created_at.strftime("%d.%m.%Y"), italic=True))
                if n.tags:
                    if meta_parts:
                        meta_parts.append(_text("  "))
                    for tag in n.tags:
                        meta_parts.append(_text(f" {tag} ", code=True))
                if meta_parts:
                    blocks.append(_paragraph(meta_parts))

                blocks.append(_paragraph([_text(n.content)]))
                blocks.append(_divider())
        else:
            blocks.append(_paragraph([_text("Заметок пока нет.", italic=True)]))

        # Tasks
        blocks.append(_heading(1, "Задачи"))
        if tasks:
            active = [t for t in tasks if t.status != "done"]
            done = [t for t in tasks if t.status == "done"]

            if active:
                blocks.append(_heading(2, "Активные"))
                for t in active:
                    icon = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}.get(t.priority, "")
                    deadline = f" — до {t.deadline.strftime('%d.%m.%Y')}" if t.deadline else ""
                    blocks.append(_todo([_text(f"{icon} {t.description}{deadline}")], checked=False))

            if done:
                blocks.append(_heading(2, "Выполненные"))
                for t in done:
                    completed = f" ({t.completed_at.strftime('%d.%m.%Y')})" if t.completed_at else ""
                    blocks.append(_todo([_text(f"{t.description}{completed}")], checked=True))
        else:
            blocks.append(_paragraph([_text("Задач пока нет.", italic=True)]))

        blocks.append(_divider())

        # Reminders
        blocks.append(_heading(1, "Напоминания"))
        if reminders:
            for r in reminders:
                time_str = r.trigger_at.strftime("%d.%m.%Y %H:%M")
                status_icon = {"active": "⏰", "triggered": "✅", "cancelled": "❌"}.get(r.status, "")
                recurring = " (повтор)" if r.is_recurring else ""
                blocks.append(_bulleted([
                    _text(f"{status_icon} {time_str}", bold=True),
                    _text(f"{recurring} — {r.text}"),
                ]))
        else:
            blocks.append(_paragraph([_text("Напоминаний пока нет.", italic=True)]))

        return blocks

    async def _get_facts(self, user_id: int) -> list[Fact]:
        result = await self.session.execute(
            select(Fact).where(Fact.user_id == user_id).order_by(Fact.category, Fact.key)
        )
        return list(result.scalars().all())

    async def _get_notes(self, user_id: int) -> list[Note]:
        result = await self.session.execute(
            select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_tasks(self, user_id: int) -> list[Task]:
        result = await self.session.execute(
            select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_reminders(self, user_id: int) -> list[Reminder]:
        result = await self.session.execute(
            select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.trigger_at.desc())
        )
        return list(result.scalars().all())
