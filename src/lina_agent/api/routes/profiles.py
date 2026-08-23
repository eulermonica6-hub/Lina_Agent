from typing import Annotated

from fastapi import APIRouter, Depends, status

from lina_agent.api.dependencies import get_candidate_repository
from lina_agent.application.repositories import CandidateProfileRepository
from lina_agent.domain.models import CandidateProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=CandidateProfile, status_code=status.HTTP_201_CREATED)
async def create_profile(
    candidate: CandidateProfile,
    repository: Annotated[CandidateProfileRepository, Depends(get_candidate_repository)],
) -> CandidateProfile:
    await repository.save(candidate)
    return candidate
