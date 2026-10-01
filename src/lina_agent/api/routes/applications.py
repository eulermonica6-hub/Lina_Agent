from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from lina_agent.api.dependencies import get_job_application_repository
from lina_agent.application.repositories import JobApplicationRepository
from lina_agent.domain.job_applications import JobApplicationRecord

router = APIRouter(prefix="/applications", tags=["job applications"])
JobApplicationRepositoryDependency = Annotated[
    JobApplicationRepository,
    Depends(get_job_application_repository),
]


class JobApplicationCreate(BaseModel):
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")


@router.get("", response_model=tuple[JobApplicationRecord, ...])
async def list_job_applications(
    repository: JobApplicationRepositoryDependency,
) -> tuple[JobApplicationRecord, ...]:
    records = await repository.list_all()
    return tuple(sorted(records, key=lambda record: record.applied_at, reverse=True))


@router.post("", response_model=JobApplicationRecord, status_code=status.HTTP_201_CREATED)
async def mark_job_applied(
    application: JobApplicationCreate,
    repository: JobApplicationRepositoryDependency,
) -> JobApplicationRecord:
    record = JobApplicationRecord(
        **application.model_dump(),
        applied_at=datetime.now(UTC),
    )
    await repository.save(record)
    return record


@router.delete("/{source_id}/{external_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unmark_job_applied(
    source_id: str,
    external_id: str,
    repository: JobApplicationRepositoryDependency,
) -> None:
    if not await repository.delete(f"{source_id}:{external_id}"):
        raise HTTPException(status_code=404, detail="Applied job not found")
