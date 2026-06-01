import io
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import settings
from bot.database.postgres import async_session
from bot.services.user_service import UserService
from bot.services.export_service import ExportService
from bot.services.notion_service import NotionService

logger = logging.getLogger(__name__)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export <format> — export user data."""
    if not context.args:
        formats = "json — все данные в JSON\ncsv — заметки и задачи в CSV\nmd — всё в Markdown"
        if settings.notion_api_token:
            formats += "\nnotion — экспорт в Notion"
        await update.message.reply_text(f"Формат: /export <json|csv|md|notion>\n\n{formats}")
        return

    fmt = context.args[0].lower()
    valid_formats = ["json", "csv", "md", "notion"]
    if fmt not in valid_formats:
        await update.message.reply_text(f"Поддерживаемые форматы: {', '.join(valid_formats)}")
        return

    if fmt == "notion":
        await _export_notion(update)
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        export_service = ExportService(session)

        if fmt == "json":
            content = await export_service.export_json(user.id)
            filename = "astra_export.json"
        elif fmt == "csv":
            content = await export_service.export_csv(user.id)
            filename = "astra_export.csv"
        else:
            content = await export_service.export_markdown(user.id)
            filename = "astra_export.md"

    file = io.BytesIO(content.encode("utf-8"))
    file.name = filename

    await update.message.reply_document(
        document=file,
        filename=filename,
        caption=f"Экспорт данных ({fmt.upper()})"
    )


async def _export_notion(update: Update) -> None:
    """Export user data to Notion."""
    if not settings.notion_api_token or not settings.notion_parent_page_id:
        await update.message.reply_text(
            "Notion не настроен. Добавьте NOTION_API_TOKEN и NOTION_PARENT_PAGE_ID в .env"
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        async with async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

            notion_service = NotionService(session)
            url = await notion_service.export_all(user.id)

        await update.message.reply_text(f"Данные экспортированы в Notion!\n{url}")
    except Exception as e:
        logger.error("Notion export failed: %s", e)
        await update.message.reply_text(f"Ошибка экспорта в Notion: {e}")
