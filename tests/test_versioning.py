import tomllib
from pathlib import Path

from lina_agent import __version__

PROJECT_ROOT = Path(__file__).parents[1]


def test_project_and_release_note_versions_match_runtime_version() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    release_notes = (PROJECT_ROOT / "releaseNote.md").read_text(encoding="utf-8")

    assert project["project"]["version"] == __version__
    assert f"## {__version__}" in release_notes
