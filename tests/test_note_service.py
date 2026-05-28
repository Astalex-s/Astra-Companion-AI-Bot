import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.database.models import Note
from bot.services.note_service import NoteService


@pytest.fixture
def mock_chroma():
    chroma = MagicMock()
    chroma.add = MagicMock()
    chroma.update = MagicMock()
    chroma.delete = MagicMock()
    chroma.query = MagicMock(return_value={"documents": [[]], "distances": [[]], "metadatas": [[]]})
    return chroma


@pytest.fixture
def note_service(mock_session, mock_chroma):
    return NoteService(mock_session, mock_chroma)


class TestCreateNote:
    @pytest.mark.asyncio
    @patch("bot.services.note_service.get_embedding", new_callable=AsyncMock)
    async def test_creates_note_with_tags(self, mock_embed, note_service, mock_session):
        """create_note should save note with AI-generated tags and vector."""
        mock_embed.return_value = [0.1] * 1536

        # Mock AI tag generation
        ai_response = MagicMock()
        ai_response.content = json.dumps({"tags": ["react", "оптимизация"], "summary": "Советы по React"})
        note_service._llm = AsyncMock()
        note_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        note = await note_service.create_note(user_id=1, text="React.memo для оптимизации")

        assert note.content == "React.memo для оптимизации"
        assert note.tags == ["react", "оптимизация"]
        assert note.summary == "Советы по React"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("bot.services.note_service.get_embedding", new_callable=AsyncMock)
    async def test_creates_note_with_failed_tags(self, mock_embed, note_service, mock_session):
        """If tag generation fails, note still saved with defaults."""
        mock_embed.return_value = [0.1] * 1536

        note_service._llm = AsyncMock()
        note_service._llm.ainvoke = AsyncMock(side_effect=Exception("AI down"))

        note = await note_service.create_note(user_id=1, text="Simple note text")

        assert note.content == "Simple note text"
        assert note.tags == []
        assert note.summary == "Simple note text"[:100]


class TestListNotes:
    @pytest.mark.asyncio
    async def test_list_notes(self, note_service, mock_session):
        """list_notes returns notes from DB."""
        mock_notes = [
            MagicMock(spec=Note, id=1, content="Note 1"),
            MagicMock(spec=Note, id=2, content="Note 2"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_notes
        mock_session.execute.return_value = mock_result

        notes = await note_service.list_notes(user_id=1)

        assert len(notes) == 2


class TestSearchNotes:
    @pytest.mark.asyncio
    @patch("bot.services.note_service.get_embedding", new_callable=AsyncMock)
    async def test_search_returns_results(self, mock_embed, note_service, mock_chroma):
        """search_notes returns scored results from ChromaDB."""
        mock_embed.return_value = [0.1] * 1536

        mock_chroma.query.return_value = {
            "documents": [["React memo tip", "Vue optimization"]],
            "distances": [[0.2, 0.6]],
            "metadatas": [[{"note_id": 1}, {"note_id": 2}]],
        }

        results = await note_service.search_notes(user_id=1, query_text="оптимизация")

        assert len(results) == 2
        assert results[0]["score"] == 0.8
        assert results[0]["note_id"] == 1

    @pytest.mark.asyncio
    @patch("bot.services.note_service.get_embedding", new_callable=AsyncMock)
    async def test_search_handles_empty(self, mock_embed, note_service, mock_chroma):
        """Empty ChromaDB results -> empty list."""
        mock_embed.return_value = [0.1] * 1536
        mock_chroma.query.return_value = {"documents": [[]], "distances": [[]], "metadatas": [[]]}

        results = await note_service.search_notes(user_id=1, query_text="ничего")

        assert results == []


class TestDeleteNote:
    @pytest.mark.asyncio
    async def test_delete_existing(self, note_service, mock_session, mock_chroma):
        """Delete existing note -> True, removed from DB and ChromaDB."""
        note = Note(id=1, user_id=1, content="test", chromadb_id="note_1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = note
        mock_session.execute.return_value = mock_result

        result = await note_service.delete_note(user_id=1, note_id=1)

        assert result is True
        mock_session.delete.assert_called_once_with(note)
        mock_chroma.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, note_service, mock_session):
        """Delete non-existent note -> False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await note_service.delete_note(user_id=1, note_id=999)

        assert result is False


class TestEditNote:
    @pytest.mark.asyncio
    @patch("bot.services.note_service.get_embedding", new_callable=AsyncMock)
    async def test_edit_existing(self, mock_embed, note_service, mock_session, mock_chroma):
        """Edit existing note -> updated content, tags, vector."""
        mock_embed.return_value = [0.1] * 1536

        note = Note(id=1, user_id=1, content="old text", chromadb_id="note_1", tags=[], summary="old")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = note
        mock_session.execute.return_value = mock_result

        ai_response = MagicMock()
        ai_response.content = json.dumps({"tags": ["new"], "summary": "Updated"})
        note_service._llm = AsyncMock()
        note_service._llm.ainvoke = AsyncMock(return_value=ai_response)

        result = await note_service.edit_note(user_id=1, note_id=1, new_text="new text")

        assert result.content == "new text"
        assert result.tags == ["new"]
        mock_chroma.update.assert_called_once()
