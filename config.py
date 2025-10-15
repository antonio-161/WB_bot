from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    DATABASE_DSN: PostgresDsn | str = Field(..., env="DATABASE_DSN")
    POLL_INTERVAL_SECONDS: int = Field(600, env="POLL_INTERVAL_SECONDS")
    DEFAULT_MAX_FREE_LINKS: int = Field(3, env="DEFAULT_MAX_FREE_LINKS")
    ADMIN_CHAT_ID: int = Field(..., env="ADMIN_CHAT_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
