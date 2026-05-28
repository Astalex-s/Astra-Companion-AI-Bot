import json
import logging
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Task
from bot.database.chromadb_client import ChromaDBClient
from bot.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)

TASK_PARSE_PROMPT = """Проанализируй описание задачи и верни JSON:
{
  "priority": "low" | "medium" | "high" | "urgent",
  "deadline": "YYYY-MM-DD HH:MM" или null если не указан
}
Определи приоритет из контекста. Если упоминается срочность — high/urgent.
Если есть дата/время — укажи дедлайн.
Отвечай ТОЛЬКО JSON."""


class TaskService:
    """CRUD operations for user tasks with AI priority detection."""

    def __init__(self, session: AsyncSession, chroma: ChromaDBClient) -> None:
        self.session = session
        self.chroma = chroma
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,
        )

    async def create_task(self, user_id: int, description: str) -> Task:
        """Create a task with AI-detected priority and deadline."""
        priority, deadline = await self._parse_task(description)

        task = Task(
            user_id=user_id,
            description=description,
            priority=priority,
            deadline=deadline,
        )
        self.session.add(task)
        await self.session.flush()

        try:
            chromadb_id = f"task_{task.id}"
            embedding = await get_embedding(description)
            self.chroma.add(
                user_id=user_id,
                data_type="tasks",
                doc_id=chromadb_id,
                text=description,
                embedding=embedding,
                metadata={"task_id": task.id, "priority": priority, "status": "todo"},
            )
            task.chromadb_id = chromadb_id
        except Exception as e:
            logger.warning("Failed to save task vector: %s", e)

        await self.session.commit()
        return task

    async def list_tasks(self, user_id: int, status: str | None = None) -> list[Task]:
        """List user tasks, optionally filtered by status."""
        query = select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        if status:
            query = query.where(Task.status == status)
        else:
            query = query.where(Task.status != "done")

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(self, user_id: int, task_id: int, new_status: str) -> Task | None:
        """Update task status."""
        result = await self.session.execute(
            select(Task).where(Task.user_id == user_id, Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None

        task.status = new_status
        if new_status == "done":
            task.completed_at = datetime.now(timezone.utc)

        await self.session.commit()
        return task

    async def delete_task(self, user_id: int, task_id: int) -> bool:
        """Delete a task."""
        result = await self.session.execute(
            select(Task).where(Task.user_id == user_id, Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False

        if task.chromadb_id:
            try:
                self.chroma.delete(user_id, "tasks", [task.chromadb_id])
            except Exception as e:
                logger.warning("Failed to delete task vector: %s", e)

        await self.session.delete(task)
        await self.session.commit()
        return True

    async def _parse_task(self, description: str) -> tuple[str, datetime | None]:
        """Use AI to detect priority and deadline from task description."""
        try:
            messages = [
                SystemMessage(content=TASK_PARSE_PROMPT),
                HumanMessage(content=description),
            ]
            response = await self._llm.ainvoke(messages)
            content = response.content.strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            data = json.loads(content)
            priority = data.get("priority", "medium")
            if priority not in ("low", "medium", "high", "urgent"):
                priority = "medium"

            deadline = None
            if data.get("deadline"):
                try:
                    deadline = datetime.strptime(data["deadline"], "%Y-%m-%d %H:%M")
                except ValueError:
                    pass

            return priority, deadline
        except Exception as e:
            logger.warning("Failed to parse task: %s", e)
            return "medium", None
