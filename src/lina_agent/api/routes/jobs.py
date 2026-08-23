from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from lina_agent.api.dependencies import get_job_repository
from lina_agent.application.repositories import JobPostingRepository
from lina_agent.domain.job_parser import parse_job_constraints
from lina_agent.domain.models import JobConstraintExtraction, JobPosting

router = APIRouter(prefix="/jobs", tags=["jobs"])


class ParseJobRequest(BaseModel):
    description: str = Field(min_length=1)


@router.post("/parse", response_model=JobConstraintExtraction)
async def parse_job(request: ParseJobRequest) -> JobConstraintExtraction:
    return parse_job_constraints(request.description, document_id=uuid4())


@router.post("", response_model=JobPosting, status_code=status.HTTP_201_CREATED)
async def create_job(
    job: JobPosting,
    repository: Annotated[JobPostingRepository, Depends(get_job_repository)],
) -> JobPosting:
    await repository.save(job)
    return job
