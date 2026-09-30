from datetime import UTC, datetime, timedelta

import pytest

from lina_agent.application.job_change_tracking import JobChangeTrackingService
from lina_agent.domain.job_changes import JobChangeKind
from lina_agent.domain.job_discovery import (
    JobLead,
    JobType,
    JobVerificationStatus,
)
from lina_agent.infrastructure.repositories.memory import InMemoryJobChangeRepository

_NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
_SOURCE_ID = "nvidia-careers"


def _lead(
    external_id: str,
    *,
    title: str = "AI Infra Intern",
    description: str = "Build AI infrastructure.",
    fingerprint: str | None = None,
    source_id: str = _SOURCE_ID,
) -> JobLead:
    return JobLead(
        lead_id=f"{source_id}:{external_id}",
        deduplication_key=f"nvidia:{external_id}",
        source_id=source_id,
        external_id=external_id,
        company="NVIDIA",
        title=title,
        job_type=JobType.INTERNSHIP,
        locations=("上海",),
        direction="AI / Machine Learning",
        source_url=f"https://example.com/{external_id}",
        captured_at=_NOW,
        verification_status=JobVerificationStatus.LIVE,
        normalized_description=description,
        content_fingerprint=fingerprint,
    )


@pytest.mark.asyncio
async def test_first_capture_is_silent_and_identical_capture_has_no_events() -> None:
    repository = InMemoryJobChangeRepository()
    service = JobChangeTrackingService(repository)
    leads = (_lead("JR1"), _lead("JR2"))

    baseline = await service.record_capture(_SOURCE_ID, leads, _NOW)
    repeated = await service.record_capture(
        _SOURCE_ID,
        leads,
        _NOW + timedelta(days=1),
    )

    assert baseline.batch.baseline is True
    assert baseline.batch.job_count == 2
    assert baseline.events == ()
    assert repeated.batch.baseline is False
    assert repeated.events == ()
    assert len(await repository.list_batches(_SOURCE_ID)) == 2
    assert await repository.list_events(_SOURCE_ID) == []


@pytest.mark.asyncio
async def test_capture_emits_new_updated_closed_and_reopened_events() -> None:
    repository = InMemoryJobChangeRepository()
    service = JobChangeTrackingService(repository)
    baseline_time = _NOW
    change_time = _NOW + timedelta(days=1)
    reopen_time = _NOW + timedelta(days=2)

    await service.record_capture(
        _SOURCE_ID,
        (_lead("JR1"), _lead("JR2", fingerprint="a" * 64)),
        baseline_time,
    )
    changed = await service.record_capture(
        _SOURCE_ID,
        (
            _lead("JR1", description="Updated responsibilities."),
            _lead("JR3"),
        ),
        change_time,
    )

    assert {event.external_id: event.kind for event in changed.events} == {
        "JR1": JobChangeKind.UPDATED,
        "JR2": JobChangeKind.CLOSED,
        "JR3": JobChangeKind.NEW,
    }
    closed = next(state for state in changed.states if state.external_id == "JR2")
    assert closed.is_open is False
    assert closed.last_seen_at == baseline_time

    still_closed = await service.record_capture(
        _SOURCE_ID,
        (
            _lead("JR1", description="Updated responsibilities."),
            _lead("JR3"),
        ),
        reopen_time,
    )
    assert still_closed.events == ()

    reopened = await service.record_capture(
        _SOURCE_ID,
        (
            _lead("JR1", description="Updated responsibilities."),
            _lead("JR2", title="Reopened role", fingerprint="b" * 64),
            _lead("JR3"),
        ),
        reopen_time + timedelta(days=1),
    )

    assert [(event.external_id, event.kind) for event in reopened.events] == [
        ("JR2", JobChangeKind.REOPENED)
    ]
    state = next(state for state in reopened.states if state.external_id == "JR2")
    assert state.first_seen_at == baseline_time
    assert state.last_seen_at == reopen_time + timedelta(days=1)
    assert state.is_open is True
    assert len(await repository.list_events(_SOURCE_ID)) == 4


@pytest.mark.asyncio
async def test_capture_rejects_foreign_source_and_duplicate_external_ids() -> None:
    service = JobChangeTrackingService(InMemoryJobChangeRepository())

    with pytest.raises(ValueError, match="tracked source"):
        await service.record_capture(
            _SOURCE_ID,
            (_lead("JR1", source_id="other-source"),),
            _NOW,
        )
    with pytest.raises(ValueError, match="unique external IDs"):
        await service.record_capture(
            _SOURCE_ID,
            (_lead("JR1"), _lead("JR1")),
            _NOW,
        )
