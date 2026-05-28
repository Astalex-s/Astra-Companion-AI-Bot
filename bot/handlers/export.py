import io

from telegram import Update
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.services.user_service import UserService
from bot.services.export_service import ExportService


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export <format> — export user data."""
    if not context.args:
        await update.message.reply_text(
            "Формат: /export <json|csv|md>\n\n"
            "json — все данные в JSON\n"
            "csv — заметки и задачи в CSV\n"
            "md — всё в Markdown"
        )
        return

    fmt = context.args[0].lower()
    if fmt not in ("json", "csv", "md"):
        await update.message.reply_text("Поддерживаемые форматы: json, csv, md")
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
