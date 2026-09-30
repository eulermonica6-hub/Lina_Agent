from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator

from lina_agent.api.dependencies import get_job_inbox_service
from lina_agent.application.job_inbox import JobInboxFilter, JobInboxService
from lina_agent.domain.job_changes import JobChangeKind, JobInboxItem

router = APIRouter(prefix="/inbox/events", tags=["job inbox"])
JobInboxServiceDependency = Annotated[JobInboxService, Depends(get_job_inbox_service)]


class JobInboxStateUpdate(BaseModel):
    saved: bool | None = None
    ignored: bool | None = None
    compare_later: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.saved is None and self.ignored is None and self.compare_later is None:
            raise ValueError("At least one inbox state field is required")
        return self


@router.get("", response_model=tuple[JobInboxItem, ...])
async def list_job_inbox(
    service: JobInboxServiceDependency,
    kind: Annotated[JobChangeKind | None, Query()] = None,
    status: Annotated[JobInboxFilter, Query()] = JobInboxFilter.UNHANDLED,
) -> tuple[JobInboxItem, ...]:
    return await service.list_items(kind=kind, state_filter=status)


@router.patch("/{event_id}", response_model=JobInboxItem)
async def update_job_inbox_state(
    event_id: UUID,
    update: JobInboxStateUpdate,
    service: JobInboxServiceDependency,
) -> JobInboxItem:
    try:
        return await service.update_state(
            event_id,
            saved=update.saved,
            ignored=update.ignored,
            compare_later=update.compare_later,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Inbox event not found") from error
