from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lina Career Agent"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    database_path: Path | None = Path("data/lina.db")

    @field_validator("database_path")
    @classmethod
    def validate_database_path(cls, value: Path | None) -> Path | None:
        if value is not None and not value.name:
            raise ValueError("database_path must point to a file")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LINA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
