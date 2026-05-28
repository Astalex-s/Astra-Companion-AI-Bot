TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Try to split at last newline within limit
        split_pos = text.rfind("\n", 0, limit)
        if split_pos == -1:
            # No newline — split at last space
            split_pos = text.rfind(" ", 0, limit)
        if split_pos == -1:
            # No space — hard split
            split_pos = limit

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks
