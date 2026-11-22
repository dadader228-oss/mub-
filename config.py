from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    BOT_TOKEN: str
    ADMIN_IDS: str = ""

    # URLs
    WEBAPP_URL: str = "https://example.com"
    API_URL: str = "https://example.com/api"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/bot_store.db"

    # Security
    SECRET_KEY: str = "change-me-in-production-please-use-long-random-string"
    INIT_DATA_MAX_AGE: int = 86400

    # Payments
    PROVIDER_TOKEN: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    WORKERS: int = 1
    RELOAD: bool = False

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
