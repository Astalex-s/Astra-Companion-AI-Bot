import logging

from bot.database.chromadb_client import ChromaDBClient
from bot.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)

DATA_TYPE_LABELS = {
    "facts": "Факт",
    "notes": "Заметка",
    "messages": "Диалог",
    "tasks": "Задача",
}

SEARCHABLE_TYPES = ["facts", "notes", "messages", "tasks"]


class SearchService:
    """Semantic search across all user data in ChromaDB."""

    def __init__(self, chroma: ChromaDBClient) -> None:
        self.chroma = chroma

    async def search_all(self, user_id: int, query: str, n_results: int = 5) -> list[dict]:
        """Search across all collections and return merged ranked results."""
        try:
            embedding = await get_embedding(query)
        except Exception as e:
            logger.warning("Failed to get embedding for search: %s", e)
            return []

        all_results = []

        for data_type in SEARCHABLE_TYPES:
            try:
                results = self.chroma.query(
                    user_id=user_id,
                    data_type=data_type,
                    query_embedding=embedding,
                    n_results=n_results,
                )

                if not results or not results.get("documents") or not results["documents"][0]:
                    continue

                distances = results.get("distances", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]

                for i, doc in enumerate(results["documents"][0]):
                    score = 1 - distances[i] if i < len(distances) else 0
                    if score <= 0.3:
                        continue
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    all_results.append({
                        "type": data_type,
                        "type_label": DATA_TYPE_LABELS.get(data_type, data_type),
                        "text": doc,
                        "score": round(score, 3),
                        "metadata": metadata,
                    })
            except Exception as e:
                logger.debug("Search in %s failed (may be empty): %s", data_type, e)

        # Sort by score descending, take top n_results
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:n_results]
