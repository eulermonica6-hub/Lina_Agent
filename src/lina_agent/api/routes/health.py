from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lina_agent import __version__
from lina_agent.config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health_check(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
    )
