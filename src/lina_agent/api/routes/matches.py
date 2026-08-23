from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from lina_agent.api.dependencies import get_candidate_repository, get_job_repository
from lina_agent.application.analyze_job import AnalyzeJobEligibility
from lina_agent.application.errors import EntityNotFoundError
from lina_agent.application.repositories import (
    CandidateProfileRepository,
    JobPostingRepository,
)
from lina_agent.domain.matching import HardConstraintResult

router = APIRouter(prefix="/matches", tags=["matches"])


class MatchRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID


@router.post("", response_model=HardConstraintResult)
async def create_match(
    request: MatchRequest,
    candidates: Annotated[CandidateProfileRepository, Depends(get_candidate_repository)],
    jobs: Annotated[JobPostingRepository, Depends(get_job_repository)],
) -> HardConstraintResult:
    service = AnalyzeJobEligibility(candidates, jobs)
    try:
        return await service.execute(request.candidate_id, request.job_id)
    except EntityNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
