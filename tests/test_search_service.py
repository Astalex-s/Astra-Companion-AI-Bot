from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.search_service import SearchService


@pytest.fixture
def mock_chroma():
    return MagicMock()


@pytest.fixture
def search_service(mock_chroma):
    return SearchService(mock_chroma)


class TestSearchAll:
    @pytest.mark.asyncio
    @patch("bot.services.search_service.get_embedding", new_callable=AsyncMock)
    async def test_merges_results_from_multiple_collections(self, mock_embed, search_service, mock_chroma):
        """Results from facts and notes merged and sorted by score."""
        mock_embed.return_value = [0.1] * 1536

        def query_side_effect(user_id, data_type, query_embedding, n_results):
            if data_type == "facts":
                return {"documents": [["имя: Алексей"]], "distances": [[0.1]], "metadatas": [[{}]]}
            if data_type == "notes":
                return {"documents": [["React tips"]], "distances": [[0.3]], "metadatas": [[{}]]}
            return {"documents": [[]], "distances": [[]], "metadatas": [[]]}

        mock_chroma.query.side_effect = query_side_effect

        results = await search_service.search_all(user_id=1, query="Алексей")

        assert len(results) == 2
        assert results[0]["score"] > results[1]["score"]
        assert results[0]["type"] == "facts"

    @pytest.mark.asyncio
    @patch("bot.services.search_service.get_embedding", new_callable=AsyncMock)
    async def test_filters_low_relevance(self, mock_embed, search_service, mock_chroma):
        """Results with score <= 0.3 excluded."""
        mock_embed.return_value = [0.1] * 1536

        mock_chroma.query.return_value = {
            "documents": [["irrelevant"]], "distances": [[0.9]], "metadatas": [[{}]]
        }

        results = await search_service.search_all(user_id=1, query="test")

        assert results == []

    @pytest.mark.asyncio
    @patch("bot.services.search_service.get_embedding", new_callable=AsyncMock)
    async def test_handles_empty_collections(self, mock_embed, search_service, mock_chroma):
        """Empty collections -> empty results, no crash."""
        mock_embed.return_value = [0.1] * 1536
        mock_chroma.query.return_value = {"documents": [[]], "distances": [[]], "metadatas": [[]]}

        results = await search_service.search_all(user_id=1, query="nothing")

        assert results == []

    @pytest.mark.asyncio
    @patch("bot.services.search_service.get_embedding", new_callable=AsyncMock)
    async def test_limits_results(self, mock_embed, search_service, mock_chroma):
        """Returns at most n_results items."""
        mock_embed.return_value = [0.1] * 1536

        docs = [f"doc_{i}" for i in range(10)]
        distances = [0.1] * 10
        metadatas = [{}] * 10
        mock_chroma.query.return_value = {
            "documents": [docs], "distances": [distances], "metadatas": [metadatas]
        }

        results = await search_service.search_all(user_id=1, query="test", n_results=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    @patch("bot.services.search_service.get_embedding", new_callable=AsyncMock)
    async def test_handles_embedding_error(self, mock_embed, search_service):
        """Embedding error -> empty results."""
        mock_embed.side_effect = Exception("API error")

        results = await search_service.search_all(user_id=1, query="test")

        assert results == []
