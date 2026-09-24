import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from lina_agent.application.agent_run_snapshot import (
    AgentRunRequestSnapshot,
    AgentRunSnapshot,
    AgentStepSnapshot,
)
from lina_agent.application.career_agent import AgentRole, AgentRunState, AgentStepStatus
from lina_agent.domain.models import CandidateProfile, EducationLevel, JobPosting
from lina_agent.infrastructure.repositories.sqlite import (
    SQLiteAgentRunSnapshotRepository,
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


@pytest.mark.asyncio
async def test_version_one_database_migrates_to_snapshot_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "lina.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE candidate_profiles (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute("PRAGMA user_version = 1")

    repository = SQLiteCandidateProfileRepository(database_path)
    await repository.list_all()

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert version == (2,)
    assert {"candidate_profiles", "job_postings", "agent_run_snapshots"} <= tables


@pytest.mark.asyncio
async def test_agent_run_snapshots_persist_in_recent_order(tmp_path: Path) -> None:
    database_path = tmp_path / "lina.db"
    repository = SQLiteAgentRunSnapshotRepository(database_path)
    older = _snapshot(datetime(2026, 9, 24, tzinfo=UTC))
    newer = _snapshot(older.created_at + timedelta(minutes=1))

    await repository.save(newer)
    await repository.save(older)

    restored = await SQLiteAgentRunSnapshotRepository(database_path).list_recent(1)
    assert restored == [newer]
    assert await repository.get(older.run_id) == older


def _snapshot(created_at: datetime) -> AgentRunSnapshot:
    return AgentRunSnapshot(
        run_id=uuid4(),
        created_at=created_at,
        state=AgentRunState.COMPLETE,
        candidate_document_id=uuid4(),
        job_catalog_document_id=uuid4(),
        total_jobs=0,
        considered_jobs=0,
        excluded_inactive_jobs=0,
        request=AgentRunRequestSnapshot(
            top_k=1,
            include_inactive=False,
            auto_decision_signals=False,
            use_llm=False,
        ),
        steps=(
            AgentStepSnapshot(
                name="ingest_resume",
                role=AgentRole.DOCUMENT_INGESTOR,
                status=AgentStepStatus.COMPLETE,
            ),
        ),
        warning_count=0,
    )
