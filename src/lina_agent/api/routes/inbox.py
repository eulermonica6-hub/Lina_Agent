from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator

from lina_agent.api.dependencies import (
    get_job_change_repository,
    get_job_inbox_service,
    get_job_monitoring_service,
)
from lina_agent.application.job_inbox import JobInboxFilter, JobInboxService
from lina_agent.application.repositories import JobChangeRepository
from lina_agent.application.weekly_monitoring import WeeklyMonitoringService
from lina_agent.domain.job_changes import JobChangeKind, JobInboxItem

router = APIRouter(prefix="/inbox/events", tags=["job inbox"])
JobInboxServiceDependency = Annotated[JobInboxService, Depends(get_job_inbox_service)]
JobChangeRepositoryDependency = Annotated[
    JobChangeRepository,
    Depends(get_job_change_repository),
]
JobMonitoringServiceDependency = Annotated[
    WeeklyMonitoringService,
    Depends(get_job_monitoring_service),
]
_SOURCE_ID = "nvidia-careers"


class JobInboxStateUpdate(BaseModel):
    saved: bool | None = None
    ignored: bool | None = None
    compare_later: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.saved is None and self.ignored is None and self.compare_later is None:
            raise ValueError("At least one inbox state field is required")
        return self


class JobMonitoringStatus(BaseModel):
    source_id: str
    source_name: str
    last_checked_at: datetime | None
    current_job_count: int
    capture_count: int
    event_count: int
    latest_event_at: datetime | None
    baseline_ready: bool


class JobMonitoringRefreshResponse(BaseModel):
    status: str
    checked_at: datetime
    current_job_count: int
    new_event_count: int


@router.get("/status", response_model=JobMonitoringStatus)
async def get_job_monitoring_status(
    repository: JobChangeRepositoryDependency,
) -> JobMonitoringStatus:
    batches = await repository.list_batches(_SOURCE_ID)
    states = await repository.list_states(_SOURCE_ID)
    events = await repository.list_events(_SOURCE_ID)
    latest_batch = max(batches, key=lambda batch: batch.captured_at, default=None)
    latest_event = max(events, key=lambda event: event.occurred_at, default=None)
    return JobMonitoringStatus(
        source_id=_SOURCE_ID,
        source_name="NVIDIA Careers",
        last_checked_at=latest_batch.captured_at if latest_batch else None,
        current_job_count=sum(state.is_open for state in states),
        capture_count=len(batches),
        event_count=len(events),
        latest_event_at=latest_event.occurred_at if latest_event else None,
        baseline_ready=bool(batches),
    )


@router.post("/refresh", response_model=JobMonitoringRefreshResponse)
async def refresh_job_monitoring(
    monitoring_service: JobMonitoringServiceDependency,
) -> JobMonitoringRefreshResponse:
    run = await monitoring_service.run()
    source = next(
        (source for source in run.sources if source.source_id == _SOURCE_ID),
        None,
    )
    if source is None:
        raise HTTPException(status_code=502, detail="NVIDIA source result unavailable")
    return JobMonitoringRefreshResponse(
        status=source.status.value,
        checked_at=source.fetched_at,
        current_job_count=len(source.leads),
        new_event_count=len(run.change_events),
    )


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
