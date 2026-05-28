from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://astra:astra_password@localhost:5432/astra_companion"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000

    # Bot settings
    bot_admin_ids: str = ""
    allowed_user_ids: str = ""
    session_timeout_minutes: int = 30
    max_context_messages: int = 20

    # Security
    encryption_key: str = ""
    rate_limit_per_minute: int = 30

    # Logging
    log_level: str = "INFO"

    @property
    def admin_ids(self) -> list[int]:
        if not self.bot_admin_ids:
            return []
        return [int(x.strip()) for x in self.bot_admin_ids.split(",") if x.strip()]

    @property
    def allowed_ids(self) -> list[int]:
        if not self.allowed_user_ids:
            return []
        return [int(x.strip()) for x in self.allowed_user_ids.split(",") if x.strip()]


settings = Settings()
