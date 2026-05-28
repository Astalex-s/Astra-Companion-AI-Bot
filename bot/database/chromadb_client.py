import chromadb

from bot.config import settings


class ChromaDBClient:
    """Wrapper over ChromaDB HTTP client for vector operations."""

    def __init__(self) -> None:
        self._client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )

    def _collection_name(self, user_id: int, data_type: str) -> str:
        return f"user_{user_id}_{data_type}"

    def _get_or_create_collection(self, user_id: int, data_type: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(user_id, data_type),
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        user_id: int,
        data_type: str,
        doc_id: str,
        text: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> None:
        """Add a document with its embedding to a user's collection."""
        collection = self._get_or_create_collection(user_id, data_type)
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def query(
        self,
        user_id: int,
        data_type: str,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Search for similar documents in a user's collection."""
        collection = self._get_or_create_collection(user_id, data_type)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete(self, user_id: int, data_type: str, doc_ids: list[str]) -> None:
        """Delete documents by IDs from a user's collection."""
        collection = self._get_or_create_collection(user_id, data_type)
        collection.delete(ids=doc_ids)

    def update(
        self,
        user_id: int,
        data_type: str,
        doc_id: str,
        text: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Update an existing document in a user's collection."""
        collection = self._get_or_create_collection(user_id, data_type)
        kwargs: dict = {"ids": [doc_id]}
        if text is not None:
            kwargs["documents"] = [text]
        if embedding is not None:
            kwargs["embeddings"] = [embedding]
        if metadata is not None:
            kwargs["metadatas"] = [metadata]
        collection.update(**kwargs)

    def count(self, user_id: int, data_type: str) -> int:
        """Return the number of documents in a user's collection."""
        collection = self._get_or_create_collection(user_id, data_type)
        return collection.count()

    def heartbeat(self) -> int:
        """Check ChromaDB server availability."""
        return self._client.heartbeat()
