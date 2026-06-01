from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.services.user_service import UserService
from bot.services.note_service import NoteService

_chroma = None

WAITING_NOTE_TEXT = 0


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handle /note [text] — create a new note or start conversation."""
    if context.args:
        # Fast mode: /note <text>
        text = " ".join(context.args)
        await _create_and_reply(update, text)
        return ConversationHandler.END

    await update.message.reply_text("Напишите текст заметки:")
    return WAITING_NOTE_TEXT


async def note_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle note text in conversation mode."""
    text = update.message.text
    if not text:
        await update.message.reply_text("Пустой текст. Попробуйте ещё раз или /cancel.")
        return WAITING_NOTE_TEXT

    await _create_and_reply(update, text)
    return ConversationHandler.END


async def _create_and_reply(update: Update, text: str) -> None:
    """Create note and send reply."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        note_service = NoteService(session, _get_chroma())
        note = await note_service.create_note(user.id, text)

    tags_str = ", ".join(note.tags) if note.tags else "нет"
    await update.message.reply_text(
        f"Заметка #{note.id} сохранена.\n"
        f"Описание: {note.summary}\n"
        f"Теги: {tags_str}"
    )


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /notes [tag] — list notes, optionally filtered by tag."""
    tag = context.args[0] if context.args else None

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        note_service = NoteService(session, _get_chroma())
        notes = await note_service.list_notes(user.id, tag=tag)

    if not notes:
        msg = "Заметок не найдено."
        if tag:
            msg += f" (тег: {tag})"
        await update.message.reply_text(msg)
        return

    lines = []
    header = "Ваши заметки"
    if tag:
        header += f" (тег: {tag})"
    lines.append(f"{header}:\n")

    for note in notes:
        tags_str = ", ".join(note.tags) if note.tags else ""
        summary = note.summary or note.content[:80]
        line = f"[{note.id}] {summary}"
        if tags_str:
            line += f" [{tags_str}]"
        lines.append(line)

    lines.append(f"\nВсего: {len(notes)}")
    await update.message.reply_text("\n".join(lines))


async def note_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /note_edit <id> <new text>."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Формат: /note_edit <id> <новый текст>")
        return

    try:
        note_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    new_text = " ".join(context.args[1:])

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        note_service = NoteService(session, _get_chroma())
        note = await note_service.edit_note(user.id, note_id, new_text)

    if note:
        await update.message.reply_text(f"Заметка #{note_id} обновлена.")
    else:
        await update.message.reply_text(f"Заметка #{note_id} не найдена.")


async def note_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /note_delete <id>."""
    if not context.args:
        await update.message.reply_text("Укажите ID: /note_delete <id>")
        return

    try:
        note_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        note_service = NoteService(session, _get_chroma())
        deleted = await note_service.delete_note(user.id, note_id)

    if deleted:
        await update.message.reply_text(f"Заметка #{note_id} удалена.")
    else:
        await update.message.reply_text(f"Заметка #{note_id} не найдена.")
