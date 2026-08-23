import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from lina_agent.application.analyze_job import AnalyzeJobEligibility
from lina_agent.application.errors import EntityNotFoundError
from lina_agent.domain.matching import HardConstraintFailure
from lina_agent.domain.models import CandidateProfile, JobPosting
from lina_agent.infrastructure.repositories.memory import (
    InMemoryCandidateProfileRepository,
    InMemoryJobPostingRepository,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_json(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text()))


async def build_service() -> tuple[AnalyzeJobEligibility, CandidateProfile, JobPosting]:
    candidate = CandidateProfile.model_validate(load_json("candidate_profile.json"))
    job = JobPosting.model_validate(load_json("target_job.json"))
    candidates = InMemoryCandidateProfileRepository()
    jobs = InMemoryJobPostingRepository()
    await candidates.save(candidate)
    await jobs.save(job)
    return AnalyzeJobEligibility(candidates, jobs), candidate, job


@pytest.mark.asyncio
async def test_target_job_rejects_anonymized_candidate_graduation_year() -> None:
    service, candidate, job = await build_service()

    result = await service.execute(candidate.id, job.id)

    assert result.is_eligible is False
    assert result.reasons == (HardConstraintFailure.GRADUATION_YEAR,)


@pytest.mark.asyncio
async def test_analyze_job_reports_missing_candidate() -> None:
    service, _, job = await build_service()

    with pytest.raises(EntityNotFoundError, match="candidate profile"):
        await service.execute(UUID(int=0), job.id)


@pytest.mark.asyncio
async def test_analyze_job_reports_missing_job() -> None:
    service, candidate, _ = await build_service()

    with pytest.raises(EntityNotFoundError, match="job posting"):
        await service.execute(candidate.id, UUID(int=0))
