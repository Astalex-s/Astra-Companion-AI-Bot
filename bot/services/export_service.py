import csv
import io
import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Note, Task, Fact

logger = logging.getLogger(__name__)


class ExportService:
    """Export user data to various file formats."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def export_json(self, user_id: int) -> str:
        """Export all user data as JSON string."""
        notes = await self._get_notes(user_id)
        tasks = await self._get_tasks(user_id)
        facts = await self._get_facts(user_id)

        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "notes": [
                {"id": n.id, "content": n.content, "summary": n.summary,
                 "tags": n.tags, "created_at": n.created_at.isoformat() if n.created_at else None}
                for n in notes
            ],
            "tasks": [
                {"id": t.id, "description": t.description, "priority": t.priority,
                 "status": t.status, "deadline": t.deadline.isoformat() if t.deadline else None,
                 "created_at": t.created_at.isoformat() if t.created_at else None}
                for t in tasks
            ],
            "facts": [
                {"id": f.id, "category": f.category, "key": f.key, "value": f.value}
                for f in facts
            ],
        }

        return json.dumps(data, ensure_ascii=False, indent=2)

    async def export_csv(self, user_id: int) -> str:
        """Export notes and tasks as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Notes
        writer.writerow(["type", "id", "content", "tags", "priority", "status", "deadline", "created_at"])

        notes = await self._get_notes(user_id)
        for n in notes:
            writer.writerow([
                "note", n.id, n.content,
                ",".join(n.tags) if n.tags else "",
                "", "", "",
                n.created_at.isoformat() if n.created_at else "",
            ])

        tasks = await self._get_tasks(user_id)
        for t in tasks:
            writer.writerow([
                "task", t.id, t.description, "",
                t.priority, t.status,
                t.deadline.isoformat() if t.deadline else "",
                t.created_at.isoformat() if t.created_at else "",
            ])

        return output.getvalue()

    async def export_markdown(self, user_id: int) -> str:
        """Export notes as Markdown string."""
        notes = await self._get_notes(user_id)
        facts = await self._get_facts(user_id)
        tasks = await self._get_tasks(user_id)

        lines = [f"# AstraCompanion Export\n"]
        lines.append(f"_Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}_\n")

        if facts:
            lines.append("## Facts\n")
            for f in facts:
                lines.append(f"- **{f.key}**: {f.value}")
            lines.append("")

        if notes:
            lines.append("## Notes\n")
            for n in notes:
                tags = f" `{'` `'.join(n.tags)}`" if n.tags else ""
                date = n.created_at.strftime("%Y-%m-%d") if n.created_at else ""
                lines.append(f"### [{date}]{tags}\n")
                lines.append(f"{n.content}\n")

        if tasks:
            lines.append("## Tasks\n")
            for t in tasks:
                check = "x" if t.status == "done" else " "
                deadline = f" (до {t.deadline.strftime('%d.%m')})" if t.deadline else ""
                lines.append(f"- [{check}] [{t.priority}] {t.description}{deadline}")
            lines.append("")

        return "\n".join(lines)

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

    async def _get_facts(self, user_id: int) -> list[Fact]:
        result = await self.session.execute(
            select(Fact).where(Fact.user_id == user_id).order_by(Fact.category, Fact.key)
        )
        return list(result.scalars().all())
