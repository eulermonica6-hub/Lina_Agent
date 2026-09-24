from pathlib import Path

import pytest
from pydantic import ValidationError

from lina_agent.config import Settings


def test_database_path_can_be_configured_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINA_DATABASE_PATH", "data/private/test-lina.db")

    settings = Settings()

    assert settings.database_path == Path("data/private/test-lina.db")


def test_database_path_can_disable_persistence() -> None:
    settings = Settings(database_path=None)

    assert settings.database_path is None


def test_empty_database_path_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_DATABASE_PATH", "")

    with pytest.raises(ValidationError, match="must point to a file"):
        Settings()
