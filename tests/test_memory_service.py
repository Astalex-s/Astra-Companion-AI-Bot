import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.chat_service import ChatService, SYSTEM_PROMPT, MEMORY_CONTEXT_HEADER


@pytest.fixture
def mock_chroma():
    chroma = MagicMock()
    return chroma


@pytest.fixture
def chat_service_with_chroma(mock_session, mock_chroma):
    return ChatService(mock_session, chroma=mock_chroma)


class TestRecallMemories:
    @pytest.mark.asyncio
    @patch("bot.services.chat_service.get_embedding", new_callable=AsyncMock)
    async def test_returns_relevant_facts(self, mock_embed, chat_service_with_chroma, mock_chroma):
        """Recall should return facts with score > 0.3."""
        mock_embed.return_value = [0.1] * 1536

        mock_chroma.query.return_value = {
            "documents": [["имя: Алексей", "профессия: программист"]],
            "distances": [[0.1, 0.5]],  # cosine distance; score = 1 - distance
        }

        result = await chat_service_with_chroma._recall_memories(user_id=1, query_text="расскажи обо мне")

        assert "имя: Алексей" in result
        assert "профессия: программист" in result

    @pytest.mark.asyncio
    @patch("bot.services.chat_service.get_embedding", new_callable=AsyncMock)
    async def test_filters_low_relevance(self, mock_embed, chat_service_with_chroma, mock_chroma):
        """Facts with score <= 0.3 should be excluded."""
        mock_embed.return_value = [0.1] * 1536

        mock_chroma.query.return_value = {
            "documents": [["что-то нерелевантное"]],
            "distances": [[0.9]],  # score = 0.1, below threshold
        }

        result = await chat_service_with_chroma._recall_memories(user_id=1, query_text="test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_without_chroma(self, mock_session):
        """Without ChromaDB client, recall returns empty string."""
        service = ChatService(mock_session, chroma=None)
        result = await service._recall_memories(user_id=1, query_text="test")

        assert result == ""

    @pytest.mark.asyncio
    @patch("bot.services.chat_service.get_embedding", new_callable=AsyncMock)
    async def test_handles_chroma_error(self, mock_embed, chat_service_with_chroma, mock_chroma):
        """ChromaDB error -> empty result, no crash."""
        mock_embed.return_value = [0.1] * 1536
        mock_chroma.query.side_effect = Exception("ChromaDB down")

        result = await chat_service_with_chroma._recall_memories(user_id=1, query_text="test")

        assert result == ""


class TestBuildContextWithMemory:
    @pytest.mark.asyncio
    @patch("bot.services.chat_service.get_embedding", new_callable=AsyncMock)
    async def test_system_prompt_includes_memories(self, mock_embed, chat_service_with_chroma, mock_session, mock_chroma):
        """When memories exist, system prompt should include them."""
        mock_embed.return_value = [0.1] * 1536

        # No session messages
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_chroma.query.return_value = {
            "documents": [["имя: Алексей"]],
            "distances": [[0.1]],
        }

        messages = await chat_service_with_chroma._build_context(1, uuid.uuid4(), "привет")

        system_msg = messages[0].content
        assert SYSTEM_PROMPT in system_msg
        assert "имя: Алексей" in system_msg

    @pytest.mark.asyncio
    async def test_system_prompt_without_memories(self, mock_session):
        """Without ChromaDB, system prompt is plain."""
        service = ChatService(mock_session, chroma=None)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        messages = await service._build_context(1, uuid.uuid4(), "привет")

        assert messages[0].content == SYSTEM_PROMPT
