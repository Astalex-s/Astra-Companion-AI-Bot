import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.chat_service import ChatService, SYSTEM_PROMPT
from bot.database.models import User, Message


@pytest.fixture
def user():
    u = User(id=1, telegram_id=123456789, username="testuser", first_name="Test")
    return u


@pytest.fixture
def chat_service(mock_session):
    return ChatService(mock_session)


class TestChatServiceGetResponse:
    @pytest.mark.asyncio
    async def test_saves_user_and_assistant_messages(self, chat_service, mock_session, user):
        """get_response should save user message, call AI, save assistant message."""
        session_id = uuid.uuid4()

        # Mock _get_or_create_session_id
        chat_service._get_or_create_session_id = AsyncMock(return_value=session_id)

        # Mock _build_context
        chat_service._build_context = AsyncMock(return_value=[])

        # Mock LLM response
        ai_response = MagicMock()
        ai_response.content = "Hello! How can I help?"
        ai_response.usage_metadata = {"total_tokens": 42}
        chat_service._llm = AsyncMock()
        chat_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        result = await chat_service.get_response(user, "Hi there")

        assert result == "Hello! How can I help?"

        # Verify user message was added
        assert mock_session.add.call_count == 2  # user msg + assistant msg
        user_msg_call = mock_session.add.call_args_list[0]
        saved_user_msg = user_msg_call[0][0]
        assert isinstance(saved_user_msg, Message)
        assert saved_user_msg.role == "user"
        assert saved_user_msg.content == "Hi there"
        assert saved_user_msg.session_id == session_id

        # Verify assistant message was added
        assistant_msg_call = mock_session.add.call_args_list[1]
        saved_assistant_msg = assistant_msg_call[0][0]
        assert isinstance(saved_assistant_msg, Message)
        assert saved_assistant_msg.role == "assistant"
        assert saved_assistant_msg.content == "Hello! How can I help?"

        # Verify commit
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_force_new_session_creates_new_uuid(self, chat_service, mock_session, user):
        """force_new_session=True should not reuse old session_id."""
        chat_service._build_context = AsyncMock(return_value=[])
        chat_service._get_or_create_session_id = AsyncMock()

        ai_response = MagicMock()
        ai_response.content = "Fresh start!"
        ai_response.usage_metadata = None
        chat_service._llm = AsyncMock()
        chat_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        await chat_service.get_response(user, "test", force_new_session=True)

        # _get_or_create_session_id should NOT be called when forcing new session
        chat_service._get_or_create_session_id.assert_not_awaited()


class TestChatServiceBuildContext:
    @pytest.mark.asyncio
    async def test_build_context_includes_system_prompt(self, chat_service, mock_session):
        """Context should always start with system prompt."""
        # Mock execute to return empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        messages = await chat_service._build_context(1, uuid.uuid4(), "test")

        assert len(messages) == 1
        assert SYSTEM_PROMPT in messages[0].content

    @pytest.mark.asyncio
    async def test_build_context_maps_roles_correctly(self, chat_service, mock_session):
        """User messages -> HumanMessage, assistant -> AIMessage."""
        msg1 = MagicMock(spec=Message)
        msg1.role = "user"
        msg1.content = "Hello"

        msg2 = MagicMock(spec=Message)
        msg2.role = "assistant"
        msg2.content = "Hi there!"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [msg1, msg2]
        mock_session.execute.return_value = mock_result

        messages = await chat_service._build_context(1, uuid.uuid4(), "test")

        assert len(messages) == 3  # system + user + assistant
        assert messages[1].content == "Hello"
        assert messages[2].content == "Hi there!"


class TestChatServiceSessionId:
    @pytest.mark.asyncio
    async def test_returns_existing_session_if_recent(self, chat_service, mock_session):
        """Should return existing session_id if last message is recent."""
        existing_id = uuid.uuid4()
        mock_msg = MagicMock()
        mock_msg.session_id = existing_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_msg
        mock_session.execute.return_value = mock_result

        result = await chat_service._get_or_create_session_id(1)

        assert result == existing_id

    @pytest.mark.asyncio
    async def test_returns_new_session_if_no_recent(self, chat_service, mock_session):
        """Should return new UUID if no recent messages."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await chat_service._get_or_create_session_id(1)

        assert isinstance(result, uuid.UUID)
