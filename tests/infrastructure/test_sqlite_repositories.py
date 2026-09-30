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
from lina_agent.application.job_change_tracking import JobChangeTrackingService
from lina_agent.application.persistence_models import (
    DocumentKind,
    create_confirmation_version,
    create_document_reference,
)
from lina_agent.domain.career_matching import CandidateAvailabilityConfirmation
from lina_agent.domain.job_changes import JobChangeKind
from lina_agent.domain.job_discovery import JobLead, JobType, JobVerificationStatus
from lina_agent.domain.models import CandidateProfile, EducationLevel, JobPosting
from lina_agent.infrastructure.document_loader import LocalDocumentLoader
from lina_agent.infrastructure.repositories.sqlite import (
    SQLiteAgentRunSnapshotRepository,
    SQLiteCandidateConfirmationVersionRepository,
    SQLiteCandidateProfileRepository,
    SQLiteDocumentReferenceRepository,
    SQLiteJobChangeRepository,
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
async def test_version_one_database_migrates_to_versioned_reference_schema(
    tmp_path: Path,
) -> None:
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
    assert version == (4,)
    assert {
        "candidate_profiles",
        "job_postings",
        "agent_run_snapshots",
        "document_references",
        "candidate_confirmation_versions",
        "job_capture_batches",
        "job_listing_states",
        "job_change_events",
    } <= tables


@pytest.mark.asyncio
async def test_job_changes_persist_across_repository_instances(tmp_path: Path) -> None:
    database_path = tmp_path / "lina.db"
    baseline_time = datetime(2026, 9, 30, tzinfo=UTC)
    change_time = baseline_time + timedelta(days=1)
    first_tracker = JobChangeTrackingService(SQLiteJobChangeRepository(database_path))

    baseline = await first_tracker.record_capture(
        "nvidia-careers",
        (_job_lead("JR1"), _job_lead("JR2")),
        baseline_time,
    )
    second_tracker = JobChangeTrackingService(SQLiteJobChangeRepository(database_path))
    changed = await second_tracker.record_capture(
        "nvidia-careers",
        (
            _job_lead("JR1", description="Updated description"),
            _job_lead("JR3"),
        ),
        change_time,
    )

    assert baseline.events == ()
    assert {event.kind for event in changed.events} == {
        JobChangeKind.NEW,
        JobChangeKind.UPDATED,
        JobChangeKind.CLOSED,
    }
    repository = SQLiteJobChangeRepository(database_path)
    assert len(await repository.list_batches("nvidia-careers")) == 2
    assert len(await repository.list_states("nvidia-careers")) == 3
    assert len(await repository.list_events("nvidia-careers")) == 3
    assert await repository.list_batches("other-source") == []


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


def _job_lead(external_id: str, description: str = "Original description") -> JobLead:
    return JobLead(
        lead_id=f"nvidia-careers:{external_id}",
        deduplication_key=f"nvidia:{external_id}",
        source_id="nvidia-careers",
        external_id=external_id,
        company="NVIDIA",
        title="AI Intern",
        job_type=JobType.INTERNSHIP,
        locations=("上海",),
        direction="AI / Machine Learning",
        source_url=f"https://example.com/{external_id}",
        captured_at=datetime(2026, 9, 30, tzinfo=UTC),
        verification_status=JobVerificationStatus.LIVE,
        normalized_description=description,
    )


def test_agent_run_snapshot_version_one_remains_readable() -> None:
    payload = _snapshot(datetime(2026, 9, 24, tzinfo=UTC)).model_dump(mode="json")
    payload["schema_version"] = 1
    payload.pop("candidate_document_reference_id")
    payload.pop("job_catalog_document_reference_id")
    payload.pop("candidate_confirmation_version_id")

    restored = AgentRunSnapshot.model_validate(payload)

    assert restored.schema_version == 1
    assert restored.candidate_document_reference_id is None
    assert restored.candidate_confirmation_version_id is None


@pytest.mark.asyncio
async def test_document_reference_is_immutable_and_confirmation_version_persists(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "lina.db"
    document = LocalDocumentLoader().load_bytes("resume.txt", b"Python")
    reference = create_document_reference(document, DocumentKind.CANDIDATE_RESUME, 6)
    changed = reference.model_copy(update={"byte_size": 999})
    document_repository = SQLiteDocumentReferenceRepository(database_path)

    await document_repository.save(reference)
    await document_repository.save(changed)

    assert await document_repository.get(reference.reference_id) == reference
    version = create_confirmation_version(
        CandidateAvailabilityConfirmation(weekly_days=5),
        None,
    )
    assert version is not None
    confirmation_repository = SQLiteCandidateConfirmationVersionRepository(database_path)
    await confirmation_repository.save(version)
    assert await confirmation_repository.get(version.version_id) == version
