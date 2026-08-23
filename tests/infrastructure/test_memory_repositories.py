from uuid import uuid4

import pytest

from lina_agent.domain.models import CandidateProfile, EducationLevel, JobPosting
from lina_agent.infrastructure.repositories.memory import (
    InMemoryCandidateProfileRepository,
    InMemoryJobPostingRepository,
)


@pytest.mark.asyncio
async def test_candidate_repository_saves_and_returns_a_copy() -> None:
    repository = InMemoryCandidateProfileRepository()
    candidate = CandidateProfile(
        graduation_year=2028,
        highest_education=EducationLevel.MASTER,
        years_of_experience=0.33,
        skills={"Python"},
        preferred_locations={"上海"},
    )

    await repository.save(candidate)
    candidate.skills.add("uncommitted mutation")
    stored = await repository.get(candidate.id)

    assert stored is not None
    assert stored.skills == {"Python"}
    assert await repository.list_all() == [stored]


@pytest.mark.asyncio
async def test_candidate_repository_returns_none_for_unknown_id() -> None:
    repository = InMemoryCandidateProfileRepository()

    assert await repository.get(uuid4()) is None


@pytest.mark.asyncio
async def test_job_repository_upserts_by_id() -> None:
    repository = InMemoryJobPostingRepository()
    job = JobPosting(title="Original", company="Example", description="First version")
    updated = job.model_copy(update={"title": "Updated"})

    await repository.save(job)
    await repository.save(updated)

    assert await repository.get(job.id) == updated
    assert await repository.list_all() == [updated]


@pytest.mark.asyncio
async def test_job_repository_returns_none_for_unknown_id() -> None:
    repository = InMemoryJobPostingRepository()

    assert await repository.get(uuid4()) is None
