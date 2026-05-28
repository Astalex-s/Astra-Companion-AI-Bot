from telegram import Update
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.services.user_service import UserService
from bot.services.task_service import TaskService

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


PRIORITY_ICONS = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task <description> — create a new task."""
    if not context.args:
        await update.message.reply_text("Укажите описание: /task <текст>")
        return

    description = " ".join(context.args)

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        task_service = TaskService(session, _get_chroma())
        task = await task_service.create_task(user.id, description)

    icon = PRIORITY_ICONS.get(task.priority, "")
    deadline_str = task.deadline.strftime("%d.%m.%Y %H:%M") if task.deadline else "не указан"
    await update.message.reply_text(
        f"Задача #{task.id} создана.\n"
        f"Приоритет: {icon} {task.priority}\n"
        f"Дедлайн: {deadline_str}"
    )


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tasks [done] — list tasks."""
    status = context.args[0] if context.args else None

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        task_service = TaskService(session, _get_chroma())
        tasks = await task_service.list_tasks(user.id, status=status)

    if not tasks:
        label = f" (статус: {status})" if status else ""
        await update.message.reply_text(f"Задач не найдено{label}.")
        return

    lines = ["Ваши задачи:\n"]
    for t in tasks:
        icon = PRIORITY_ICONS.get(t.priority, "")
        status_icon = {"todo": "[ ]", "in_progress": "[~]", "done": "[x]"}.get(t.status, "[ ]")
        line = f"{status_icon} [{t.id}] {icon} {t.description[:80]}"
        if t.deadline:
            line += f" (до {t.deadline.strftime('%d.%m')})"
        lines.append(line)

    lines.append(f"\nВсего: {len(tasks)}")
    await update.message.reply_text("\n".join(lines))


async def task_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task_done <id>."""
    if not context.args:
        await update.message.reply_text("Укажите ID: /task_done <id>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        task_service = TaskService(session, _get_chroma())
        task = await task_service.update_status(user.id, task_id, "done")

    if task:
        await update.message.reply_text(f"Задача #{task_id} выполнена!")
    else:
        await update.message.reply_text(f"Задача #{task_id} не найдена.")


async def task_progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task_progress <id>."""
    if not context.args:
        await update.message.reply_text("Укажите ID: /task_progress <id>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        task_service = TaskService(session, _get_chroma())
        task = await task_service.update_status(user.id, task_id, "in_progress")

    if task:
        await update.message.reply_text(f"Задача #{task_id} в работе.")
    else:
        await update.message.reply_text(f"Задача #{task_id} не найдена.")


async def task_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task_delete <id>."""
    if not context.args:
        await update.message.reply_text("Укажите ID: /task_delete <id>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        task_service = TaskService(session, _get_chroma())
        deleted = await task_service.delete_task(user.id, task_id)

    if deleted:
        await update.message.reply_text(f"Задача #{task_id} удалена.")
    else:
        await update.message.reply_text(f"Задача #{task_id} не найдена.")
