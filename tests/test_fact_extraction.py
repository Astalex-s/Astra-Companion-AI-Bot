import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.database.models import Fact
from bot.services.fact_extraction import FactExtractionService


@pytest.fixture
def mock_chroma():
    chroma = MagicMock()
    chroma.add = MagicMock()
    chroma.update = MagicMock()
    chroma.delete = MagicMock()
    chroma.query = MagicMock(return_value={"documents": [[]], "distances": [[]]})
    return chroma


@pytest.fixture
def fact_service(mock_session, mock_chroma):
    return FactExtractionService(mock_session, mock_chroma)


class TestExtractFacts:
    @pytest.mark.asyncio
    async def test_extracts_facts_from_ai_response(self, fact_service):
        """AI returns valid JSON -> parsed into list of dicts."""
        ai_response = MagicMock()
        ai_response.content = json.dumps([
            {"category": "personal_info", "key": "имя", "value": "Алексей", "confidence": 0.95}
        ])
        fact_service._llm = AsyncMock()
        fact_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        facts = await fact_service._extract_facts("Привет, меня зовут Алексей")

        assert len(facts) == 1
        assert facts[0]["key"] == "имя"
        assert facts[0]["value"] == "Алексей"

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_facts(self, fact_service):
        """AI returns empty list -> empty result."""
        ai_response = MagicMock()
        ai_response.content = "[]"
        fact_service._llm = AsyncMock()
        fact_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        facts = await fact_service._extract_facts("Который час?")

        assert facts == []

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, fact_service):
        """AI returns garbage -> empty result, no crash."""
        ai_response = MagicMock()
        ai_response.content = "not valid json at all"
        fact_service._llm = AsyncMock()
        fact_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        facts = await fact_service._extract_facts("something")

        assert facts == []

    @pytest.mark.asyncio
    async def test_strips_markdown_code_block(self, fact_service):
        """AI wraps JSON in ```json ... ``` -> still parsed correctly."""
        ai_response = MagicMock()
        ai_response.content = '```json\n[{"category": "skill", "key": "язык", "value": "Python", "confidence": 0.9}]\n```'
        fact_service._llm = AsyncMock()
        fact_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        facts = await fact_service._extract_facts("Я пишу на Python")

        assert len(facts) == 1
        assert facts[0]["value"] == "Python"


class TestUpsertFact:
    @pytest.mark.asyncio
    @patch("bot.services.fact_extraction.get_embedding", new_callable=AsyncMock)
    async def test_creates_new_fact(self, mock_embed, fact_service, mock_session):
        """New fact -> saved to DB + ChromaDB."""
        mock_embed.return_value = [0.1] * 1536

        # No existing fact
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        fact_data = {"category": "personal_info", "key": "имя", "value": "Алексей", "confidence": 0.95}

        fact = await fact_service._upsert_fact(user_id=1, fact_data=fact_data, message_id=10)

        assert fact is not None
        assert fact.key == "имя"
        assert fact.value == "Алексей"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.services.fact_extraction.get_embedding", new_callable=AsyncMock)
    async def test_updates_existing_fact(self, mock_embed, fact_service, mock_session):
        """Existing fact with same key -> updated, not duplicated."""
        mock_embed.return_value = [0.1] * 1536

        existing = Fact(
            id=5, user_id=1, category="personal_info",
            key="имя", value="Алекс", confidence=0.8,
            chromadb_id="fact_5",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        fact_data = {"category": "personal_info", "key": "имя", "value": "Алексей", "confidence": 0.95}

        fact = await fact_service._upsert_fact(user_id=1, fact_data=fact_data, message_id=None)

        assert fact.value == "Алексей"
        assert fact.confidence == 0.95
        # Should NOT call session.add (update, not insert)
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_empty_key_or_value(self, fact_service, mock_session):
        """Facts with empty key or value -> skipped."""
        result = await fact_service._upsert_fact(1, {"category": "other", "key": "", "value": "x"}, None)
        assert result is None

        result = await fact_service._upsert_fact(1, {"category": "other", "key": "x", "value": ""}, None)
        assert result is None


class TestDeleteFacts:
    @pytest.mark.asyncio
    async def test_delete_fact_success(self, fact_service, mock_session):
        """Delete existing fact -> returns True."""
        fact = Fact(id=1, user_id=1, category="other", key="x", value="y", chromadb_id="fact_1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fact
        mock_session.execute.return_value = mock_result

        result = await fact_service.delete_fact(user_id=1, fact_id=1)

        assert result is True
        mock_session.delete.assert_called_once_with(fact)

    @pytest.mark.asyncio
    async def test_delete_fact_not_found(self, fact_service, mock_session):
        """Delete non-existent fact -> returns False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await fact_service.delete_fact(user_id=1, fact_id=999)

        assert result is False
