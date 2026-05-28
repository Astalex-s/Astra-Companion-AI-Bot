import logging

from cryptography.fernet import Fernet, InvalidToken

from bot.config import settings

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet() -> Fernet | None:
    """Get Fernet cipher instance. Returns None if no key configured."""
    global _fernet
    if _fernet is not None:
        return _fernet

    if not settings.encryption_key:
        return None

    try:
        _fernet = Fernet(settings.encryption_key.encode())
        return _fernet
    except Exception as e:
        logger.error("Invalid encryption key: %s", e)
        return None


def encrypt(text: str) -> str:
    """Encrypt text. Returns original text if encryption is not configured."""
    f = _get_fernet()
    if not f:
        return text
    return f.encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    """Decrypt text. Returns original text if decryption fails."""
    f = _get_fernet()
    if not f:
        return text
    try:
        return f.decrypt(text.encode()).decode()
    except InvalidToken:
        return text


def generate_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()
