import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.database.models import Task
from bot.services.task_service import TaskService


@pytest.fixture
def mock_chroma():
    chroma = MagicMock()
    chroma.add = MagicMock()
    chroma.delete = MagicMock()
    return chroma


@pytest.fixture
def task_service(mock_session, mock_chroma):
    return TaskService(mock_session, mock_chroma)


class TestCreateTask:
    @pytest.mark.asyncio
    @patch("bot.services.task_service.get_embedding", new_callable=AsyncMock)
    async def test_creates_task_with_ai_priority(self, mock_embed, task_service, mock_session):
        """create_task saves task with AI-detected priority."""
        mock_embed.return_value = [0.1] * 1536

        ai_response = MagicMock()
        ai_response.content = json.dumps({"priority": "high", "deadline": "2026-06-01 10:00"})
        task_service._llm = AsyncMock()
        task_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        task = await task_service.create_task(user_id=1, description="Сдать отчёт до пятницы")

        assert task.description == "Сдать отчёт до пятницы"
        assert task.priority == "high"
        assert task.deadline == datetime(2026, 6, 1, 10, 0)
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.services.task_service.get_embedding", new_callable=AsyncMock)
    async def test_defaults_on_parse_failure(self, mock_embed, task_service, mock_session):
        """If AI parsing fails, defaults to medium priority, no deadline."""
        mock_embed.return_value = [0.1] * 1536

        task_service._llm = AsyncMock()
        task_service._llm.ainvoke = AsyncMock(side_effect=Exception("AI down"))

        task = await task_service.create_task(user_id=1, description="Simple task")

        assert task.priority == "medium"
        assert task.deadline is None


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_mark_done(self, task_service, mock_session):
        """update_status to done sets completed_at."""
        task = Task(id=1, user_id=1, description="test", status="todo")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = task
        mock_session.execute.return_value = mock_result

        result = await task_service.update_status(user_id=1, task_id=1, new_status="done")

        assert result.status == "done"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_not_found(self, task_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await task_service.update_status(user_id=1, task_id=999, new_status="done")

        assert result is None


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_existing(self, task_service, mock_session, mock_chroma):
        task = Task(id=1, user_id=1, description="test", chromadb_id="task_1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = task
        mock_session.execute.return_value = mock_result

        result = await task_service.delete_task(user_id=1, task_id=1)

        assert result is True
        mock_session.delete.assert_called_once()
        mock_chroma.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, task_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await task_service.delete_task(user_id=1, task_id=999)

        assert result is False
