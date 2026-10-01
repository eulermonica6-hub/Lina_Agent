from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from lina_agent import __version__
from lina_agent.api.routes import agent, discovery, health, inbox, jobs, matches, profiles
from lina_agent.application.conversational_assistant import ConversationalAssistantService
from lina_agent.application.job_discovery import JobDiscoveryService
from lina_agent.application.job_inbox import JobInboxService
from lina_agent.application.repositories import (
    AgentRunSnapshotRepository,
    CandidateConfirmationVersionRepository,
    CandidateProfileRepository,
    DocumentReferenceRepository,
    JobChangeRepository,
    JobPostingRepository,
)
from lina_agent.config import Settings, get_settings
from lina_agent.infrastructure.job_sources.nvidia_workday import NvidiaWorkdayJobSource
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES
from lina_agent.infrastructure.job_sources.verified_snapshot import VerifiedSnapshotJobSource
from lina_agent.infrastructure.repositories.memory import (
    InMemoryAgentRunSnapshotRepository,
    InMemoryCandidateConfirmationVersionRepository,
    InMemoryCandidateProfileRepository,
    InMemoryDocumentReferenceRepository,
    InMemoryJobChangeRepository,
    InMemoryJobPostingRepository,
)
from lina_agent.infrastructure.repositories.sqlite import (
    SQLiteAgentRunSnapshotRepository,
    SQLiteCandidateConfirmationVersionRepository,
    SQLiteCandidateProfileRepository,
    SQLiteDocumentReferenceRepository,
    SQLiteJobChangeRepository,
    SQLiteJobPostingRepository,
)

WEB_DIRECTORY = Path(__file__).parent / "web"
WORKBENCH_TEMPLATE = (WEB_DIRECTORY / "index.html").read_text(encoding="utf-8")
INBOX_TEMPLATE = (WEB_DIRECTORY / "inbox.html").read_text(encoding="utf-8")


def _render_page(page_mode: str) -> HTMLResponse:
    content = WORKBENCH_TEMPLATE.replace("{{APP_VERSION}}", __version__)
    return HTMLResponse(content.replace("{{PAGE_MODE}}", page_mode))


async def serve_home() -> HTMLResponse:
    return _render_page("home-page")


async def serve_workbench() -> HTMLResponse:
    return _render_page("workbench-page")


async def serve_inbox() -> HTMLResponse:
    return HTMLResponse(INBOX_TEMPLATE.replace("{{APP_VERSION}}", __version__))


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    (
        candidate_repository,
        job_repository,
        agent_run_repository,
        document_reference_repository,
        confirmation_version_repository,
        job_change_repository,
    ) = _create_repositories(app_settings)

    def settings_override() -> Settings:
        return app_settings

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        debug=app_settings.debug,
    )
    app.state.candidate_repository = candidate_repository
    app.state.job_repository = job_repository
    app.state.agent_run_repository = agent_run_repository
    app.state.document_reference_repository = document_reference_repository
    app.state.confirmation_version_repository = confirmation_version_repository
    app.state.job_change_repository = job_change_repository
    app.state.job_inbox_service = JobInboxService(job_change_repository)
    snapshot_source = VerifiedSnapshotJobSource()
    app.state.job_recommendation_service = JobDiscoveryService((snapshot_source,))
    search_sources = (snapshot_source,)
    if app_settings.environment != "test":
        search_sources = (*search_sources, NvidiaWorkdayJobSource())
    app.state.job_search_service = JobDiscoveryService(search_sources)
    app.state.conversational_assistant = ConversationalAssistantService(
        app.state.job_search_service,
        app.state.job_recommendation_service,
        app.state.job_inbox_service,
        company_names=tuple(source.company for source in MONITORED_JOB_SOURCES),
    )
    app.dependency_overrides[get_settings] = settings_override
    app.include_router(health.router)
    app.include_router(profiles.router)
    app.include_router(jobs.router)
    app.include_router(matches.router)
    app.include_router(agent.router)
    app.include_router(discovery.router)
    app.include_router(inbox.router)
    app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY), name="assets")
    app.add_api_route("/", serve_home, methods=["GET"], include_in_schema=False)
    app.add_api_route("/workbench", serve_workbench, methods=["GET"], include_in_schema=False)
    app.add_api_route("/inbox", serve_inbox, methods=["GET"], include_in_schema=False)
    return app


def _create_repositories(
    settings: Settings,
) -> tuple[
    CandidateProfileRepository,
    JobPostingRepository,
    AgentRunSnapshotRepository,
    DocumentReferenceRepository,
    CandidateConfirmationVersionRepository,
    JobChangeRepository,
]:
    if settings.environment == "test" or settings.database_path is None:
        return (
            InMemoryCandidateProfileRepository(),
            InMemoryJobPostingRepository(),
            InMemoryAgentRunSnapshotRepository(),
            InMemoryDocumentReferenceRepository(),
            InMemoryCandidateConfirmationVersionRepository(),
            InMemoryJobChangeRepository(),
        )
    return (
        SQLiteCandidateProfileRepository(settings.database_path),
        SQLiteJobPostingRepository(settings.database_path),
        SQLiteAgentRunSnapshotRepository(settings.database_path),
        SQLiteDocumentReferenceRepository(settings.database_path),
        SQLiteCandidateConfirmationVersionRepository(settings.database_path),
        SQLiteJobChangeRepository(settings.database_path),
    )


app = create_app()
