from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Telegram ---
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    ADMIN_CHAT_ID: int = Field(..., env="ADMIN_CHAT_ID")

    # --- Database ---
    POSTGRES_USER: str = Field(..., env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(..., env="POSTGRES_DB")
    DATABASE_DSN: PostgresDsn | str = Field(..., env="DATABASE_DSN")

    # --- System settings ---
    POLL_INTERVAL_SECONDS: int = Field(600, env="POLL_INTERVAL_SECONDS")
    DEFAULT_MAX_FREE_LINKS: int = Field(5, env="DEFAULT_MAX_FREE_LINKS")

    # --- Logging ---
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
