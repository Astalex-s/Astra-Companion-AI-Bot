import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Note
from bot.database.chromadb_client import ChromaDBClient
from bot.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)

TAG_PROMPT = """Проанализируй текст заметки и верни JSON с двумя полями:
- "tags": массив из 1-5 тегов на русском (строчные буквы, без #)
- "summary": краткое описание заметки (1 предложение, до 100 символов)

Отвечай ТОЛЬКО JSON, без пояснений.

Текст заметки: """


class NoteService:
    """CRUD operations for user notes with vector search."""

    def __init__(self, session: AsyncSession, chroma: ChromaDBClient) -> None:
        self.session = session
        self.chroma = chroma
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,
        )

    async def create_note(self, user_id: int, text: str) -> Note:
        """Create a note with AI-generated tags and summary."""
        tags, summary = await self._generate_tags_and_summary(text)

        note = Note(
            user_id=user_id,
            content=text,
            summary=summary,
            tags=tags,
        )
        self.session.add(note)
        await self.session.flush()

        # Save vector
        try:
            chromadb_id = f"note_{note.id}"
            embedding = await get_embedding(text)
            self.chroma.add(
                user_id=user_id,
                data_type="notes",
                doc_id=chromadb_id,
                text=text,
                embedding=embedding,
                metadata={"note_id": note.id, "tags": json.dumps(tags, ensure_ascii=False)},
            )
            note.chromadb_id = chromadb_id
        except Exception as e:
            logger.warning("Failed to save note vector: %s", e)

        await self.session.commit()
        return note

    async def list_notes(self, user_id: int, tag: str | None = None, limit: int = 20) -> list[Note]:
        """List user notes, optionally filtered by tag."""
        query = select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc()).limit(limit)

        if tag:
            query = query.where(Note.tags.contains([tag]))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_notes(self, user_id: int, query_text: str, n_results: int = 5) -> list[dict]:
        """Semantic search through notes via ChromaDB."""
        try:
            embedding = await get_embedding(query_text)
            results = self.chroma.query(
                user_id=user_id, data_type="notes",
                query_embedding=embedding, n_results=n_results,
            )

            if not results or not results.get("documents") or not results["documents"][0]:
                return []

            found = []
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i, doc in enumerate(results["documents"][0]):
                score = 1 - distances[i] if i < len(distances) else 0
                metadata = metadatas[i] if i < len(metadatas) else {}
                found.append({
                    "text": doc,
                    "score": round(score, 3),
                    "note_id": metadata.get("note_id"),
                })

            return found
        except Exception as e:
            logger.warning("Note search failed: %s", e)
            return []

    async def edit_note(self, user_id: int, note_id: int, new_text: str) -> Note | None:
        """Edit an existing note."""
        result = await self.session.execute(
            select(Note).where(Note.user_id == user_id, Note.id == note_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            return None

        note.content = new_text
        tags, summary = await self._generate_tags_and_summary(new_text)
        note.tags = tags
        note.summary = summary

        # Update vector
        if note.chromadb_id:
            try:
                embedding = await get_embedding(new_text)
                self.chroma.update(
                    user_id=user_id, data_type="notes",
                    doc_id=note.chromadb_id, text=new_text,
                    embedding=embedding,
                    metadata={"note_id": note.id, "tags": json.dumps(tags, ensure_ascii=False)},
                )
            except Exception as e:
                logger.warning("Failed to update note vector: %s", e)

        await self.session.commit()
        return note

    async def delete_note(self, user_id: int, note_id: int) -> bool:
        """Delete a note."""
        result = await self.session.execute(
            select(Note).where(Note.user_id == user_id, Note.id == note_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            return False

        if note.chromadb_id:
            try:
                self.chroma.delete(user_id, "notes", [note.chromadb_id])
            except Exception as e:
                logger.warning("Failed to delete note vector: %s", e)

        await self.session.delete(note)
        await self.session.commit()
        return True

    async def _generate_tags_and_summary(self, text: str) -> tuple[list[str], str]:
        """Use AI to generate tags and summary for a note."""
        try:
            messages = [
                SystemMessage(content=TAG_PROMPT),
                HumanMessage(content=text),
            ]
            response = await self._llm.ainvoke(messages)
            content = response.content.strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            data = json.loads(content)
            tags = data.get("tags", [])[:5]
            summary = data.get("summary", text[:100])
            return tags, summary
        except Exception as e:
            logger.warning("Failed to generate tags/summary: %s", e)
            return [], text[:100]
