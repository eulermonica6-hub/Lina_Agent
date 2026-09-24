from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from lina_agent import __version__
from lina_agent.api.routes import agent, health, jobs, matches, profiles
from lina_agent.application.repositories import CandidateProfileRepository, JobPostingRepository
from lina_agent.config import Settings, get_settings
from lina_agent.infrastructure.repositories.memory import (
    InMemoryCandidateProfileRepository,
    InMemoryJobPostingRepository,
)
from lina_agent.infrastructure.repositories.sqlite import (
    SQLiteCandidateProfileRepository,
    SQLiteJobPostingRepository,
)

WEB_DIRECTORY = Path(__file__).parent / "web"
WORKBENCH_TEMPLATE = (WEB_DIRECTORY / "index.html").read_text(encoding="utf-8")


async def serve_workbench() -> HTMLResponse:
    return HTMLResponse(WORKBENCH_TEMPLATE.replace("{{APP_VERSION}}", __version__))


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    candidate_repository, job_repository = _create_repositories(app_settings)

    def settings_override() -> Settings:
        return app_settings

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        debug=app_settings.debug,
    )
    app.state.candidate_repository = candidate_repository
    app.state.job_repository = job_repository
    app.dependency_overrides[get_settings] = settings_override
    app.include_router(health.router)
    app.include_router(profiles.router)
    app.include_router(jobs.router)
    app.include_router(matches.router)
    app.include_router(agent.router)
    app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY), name="assets")
    app.add_api_route("/", serve_workbench, methods=["GET"], include_in_schema=False)
    return app


def _create_repositories(
    settings: Settings,
) -> tuple[CandidateProfileRepository, JobPostingRepository]:
    if settings.environment == "test" or settings.database_path is None:
        return InMemoryCandidateProfileRepository(), InMemoryJobPostingRepository()
    return (
        SQLiteCandidateProfileRepository(settings.database_path),
        SQLiteJobPostingRepository(settings.database_path),
    )


app = create_app()
