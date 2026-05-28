from telegram import Update
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.services.user_service import UserService
from bot.services.fact_extraction import FactExtractionService

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


CATEGORY_LABELS = {
    "personal_info": "Личная информация",
    "preference": "Предпочтения",
    "skill": "Навыки",
    "goal": "Цели",
    "hobby": "Хобби",
    "other": "Другое",
}


async def facts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /facts — show all saved facts about the user."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(
            telegram_id=update.effective_user.id,
        )
        fact_service = FactExtractionService(session, _get_chroma())
        facts = await fact_service.get_user_facts(user.id)

    if not facts:
        await update.message.reply_text("У меня пока нет сохранённых фактов о вас.")
        return

    lines = ["Что я знаю о вас:\n"]
    for fact in facts:
        label = CATEGORY_LABELS.get(fact.category, fact.category)
        lines.append(f"[{fact.id}] {label}: {fact.key} = {fact.value}")

    lines.append(f"\nВсего: {len(facts)} фактов")
    lines.append("Удалить: /forget <id> или /forget_all")
    await update.message.reply_text("\n".join(lines))


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /forget <id> — delete a specific fact."""
    if not context.args:
        await update.message.reply_text("Укажите ID факта: /forget <id>")
        return

    try:
        fact_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(
            telegram_id=update.effective_user.id,
        )
        fact_service = FactExtractionService(session, _get_chroma())
        deleted = await fact_service.delete_fact(user.id, fact_id)

    if deleted:
        await update.message.reply_text(f"Факт #{fact_id} удалён.")
    else:
        await update.message.reply_text(f"Факт #{fact_id} не найден.")


async def forget_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /forget_all — delete all facts."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(
            telegram_id=update.effective_user.id,
        )
        fact_service = FactExtractionService(session, _get_chroma())
        count = await fact_service.delete_all_facts(user.id)

    await update.message.reply_text(f"Удалено фактов: {count}. Память очищена.")
