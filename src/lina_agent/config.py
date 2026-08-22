from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lina Career Agent"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LINA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
