from telegram import Update
from telegram.ext import ContextTypes

from bot.database.chromadb_client import ChromaDBClient
from bot.services.search_service import SearchService
from bot.database.postgres import async_session
from bot.services.user_service import UserService

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query> — semantic search across all data."""
    if not context.args:
        await update.message.reply_text("Укажите запрос: /search <текст>")
        return

    query = " ".join(context.args)

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

    search_service = SearchService(_get_chroma())
    results = await search_service.search_all(user.id, query)

    if not results:
        await update.message.reply_text("Ничего не найдено по вашему запросу.")
        return

    lines = [f"Результаты поиска по «{query}»:\n"]
    for i, r in enumerate(results, 1):
        text_preview = r["text"][:150]
        if len(r["text"]) > 150:
            text_preview += "..."
        lines.append(f"{i}. [{r['type_label']}] (релевантность: {r['score']})")
        lines.append(f"   {text_preview}\n")

    await update.message.reply_text("\n".join(lines))
