import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.database.models import Reminder
from bot.services.reminder_service import ReminderService


@pytest.fixture
def reminder_service(mock_session):
    return ReminderService(mock_session)


class TestCreateReminder:
    @pytest.mark.asyncio
    async def test_creates_reminder_from_parsed_time(self, reminder_service, mock_session):
        """Successfully parsed time -> reminder created."""
        ai_response = MagicMock()
        ai_response.content = json.dumps({
            "trigger_at": "2026-06-01 10:00",
            "text": "позвонить маме",
            "is_recurring": False,
            "recurrence_rule": None,
        })
        reminder_service._llm = AsyncMock()
        reminder_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        # Mock refresh to set id
        async def fake_refresh(obj):
            obj.id = 1
        mock_session.refresh = fake_refresh

        reminder = await reminder_service.create_reminder(user_id=1, text="через 2 часа позвонить маме")

        assert reminder is not None
        assert reminder.text == "позвонить маме"
        assert reminder.trigger_at.year == 2026
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_unparseable(self, reminder_service):
        """Unparseable time -> returns None."""
        ai_response = MagicMock()
        ai_response.content = json.dumps({"trigger_at": None, "text": "что-то"})
        reminder_service._llm = AsyncMock()
        reminder_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        result = await reminder_service.create_reminder(user_id=1, text="непонятно когда")

        assert result is None


class TestGetDueReminders:
    @pytest.mark.asyncio
    async def test_returns_due_reminders(self, reminder_service, mock_session):
        """Returns reminders with trigger_at <= now."""
        past = Reminder(id=1, user_id=1, text="test", trigger_at=datetime.now(timezone.utc) - timedelta(minutes=5), status="active")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [past]
        mock_session.execute.return_value = mock_result

        due = await reminder_service.get_due_reminders()

        assert len(due) == 1


class TestSnooze:
    @pytest.mark.asyncio
    async def test_snooze_updates_time(self, reminder_service, mock_session):
        """Snooze sets new trigger_at and status=active."""
        reminder = Reminder(id=1, user_id=1, text="test", trigger_at=datetime.now(timezone.utc), status="triggered")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_session.execute.return_value = mock_result

        new_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        result = await reminder_service.snooze(reminder_id=1, new_trigger_at=new_time)

        assert result.trigger_at == new_time
        assert result.status == "active"


class TestDeleteReminder:
    @pytest.mark.asyncio
    async def test_delete_existing(self, reminder_service, mock_session):
        reminder = Reminder(id=1, user_id=1, text="test", trigger_at=datetime.now(timezone.utc))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_session.execute.return_value = mock_result

        result = await reminder_service.delete_reminder(user_id=1, reminder_id=1)

        assert result is True
        mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, reminder_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await reminder_service.delete_reminder(user_id=1, reminder_id=999)

        assert result is False
