from fastapi import FastAPI

from lina_agent import __version__
from lina_agent.api.routes import health
from lina_agent.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    def settings_override() -> Settings:
        return app_settings

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        debug=app_settings.debug,
    )
    app.dependency_overrides[get_settings] = settings_override
    app.include_router(health.router)
    return app


app = create_app()
