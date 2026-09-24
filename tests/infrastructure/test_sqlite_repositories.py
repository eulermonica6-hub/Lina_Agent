import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from lina_agent.domain.models import CandidateProfile, EducationLevel, JobPosting
from lina_agent.infrastructure.repositories.sqlite import (
    SQLiteCandidateProfileRepository,
    SQLiteJobPostingRepository,
)


@pytest.mark.asyncio
async def test_candidate_persists_across_repository_instances(tmp_path: Path) -> None:
    database_path = tmp_path / "lina.db"
    candidate = CandidateProfile(
        graduation_year=2028,
        highest_education=EducationLevel.MASTER,
        years_of_experience=0.33,
        skills={"Python", "PyTorch"},
        preferred_locations={"上海"},
    )

    await SQLiteCandidateProfileRepository(database_path).save(candidate)
    restored = await SQLiteCandidateProfileRepository(database_path).get(candidate.id)

    assert restored == candidate
    assert await SQLiteCandidateProfileRepository(database_path).list_all() == [candidate]


@pytest.mark.asyncio
async def test_job_upsert_persists_and_unknown_id_returns_none(tmp_path: Path) -> None:
    database_path = tmp_path / "lina.db"
    job = JobPosting(title="Original", company="Example", description="First version")
    updated = job.model_copy(update={"title": "Updated"})
    first_repository = SQLiteJobPostingRepository(database_path)

    await first_repository.save(job)
    await first_repository.save(updated)
    second_repository = SQLiteJobPostingRepository(database_path)

    assert await second_repository.get(job.id) == updated
    assert await second_repository.get(uuid4()) is None
    assert await second_repository.list_all() == [updated]


@pytest.mark.asyncio
async def test_concurrent_candidate_writes_are_persisted(tmp_path: Path) -> None:
    repository = SQLiteCandidateProfileRepository(tmp_path / "lina.db")
    candidates = tuple(
        CandidateProfile(
            graduation_year=2028,
            highest_education=EducationLevel.MASTER,
            years_of_experience=0,
            skills={f"skill-{index}"},
        )
        for index in range(10)
    )

    await asyncio.gather(*(repository.save(candidate) for candidate in candidates))

    restored = await SQLiteCandidateProfileRepository(tmp_path / "lina.db").list_all()
    assert {candidate.id for candidate in restored} == {candidate.id for candidate in candidates}
