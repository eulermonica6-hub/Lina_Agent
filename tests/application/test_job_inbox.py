from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lina_agent.application.job_inbox import JobInboxFilter, JobInboxService
from lina_agent.domain.job_changes import (
    JobCaptureBatch,
    JobChangeEvent,
    JobChangeKind,
)
from lina_agent.infrastructure.repositories.memory import InMemoryJobChangeRepository

_NOW = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)


async def _repository_with_events() -> tuple[
    InMemoryJobChangeRepository,
    JobChangeEvent,
    JobChangeEvent,
]:
    repository = InMemoryJobChangeRepository()
    batch = JobCaptureBatch(
        source_id="nvidia-careers",
        captured_at=_NOW,
        job_count=2,
    )
    older = JobChangeEvent(
        event_id=uuid4(),
        batch_id=batch.batch_id,
        source_id="nvidia-careers",
        external_id="JR1",
        kind=JobChangeKind.NEW,
        occurred_at=_NOW,
        current_fingerprint="a" * 64,
        title="AI Intern",
        source_url="https://example.com/JR1",
    )
    newer = JobChangeEvent(
        event_id=uuid4(),
        batch_id=batch.batch_id,
        source_id="nvidia-careers",
        external_id="JR2",
        kind=JobChangeKind.UPDATED,
        occurred_at=_NOW + timedelta(minutes=1),
        previous_fingerprint="b" * 64,
        current_fingerprint="c" * 64,
        title="CUDA Intern",
        source_url="https://example.com/JR2",
    )
    await repository.save_capture(batch, (), (older, newer))
    return repository, older, newer


@pytest.mark.asyncio
async def test_inbox_defaults_to_unhandled_and_reads_are_side_effect_free() -> None:
    repository, older, newer = await _repository_with_events()
    service = JobInboxService(repository, clock=lambda: _NOW)

    first = await service.list_items()
    second = await service.list_items()

    assert [item.event_id for item in first] == [newer.event_id, older.event_id]
    assert second == first
    assert await repository.get_inbox_state(older.event_id) is None


@pytest.mark.asyncio
async def test_inbox_filters_kind_and_independent_user_flags() -> None:
    repository, older, newer = await _repository_with_events()
    service = JobInboxService(repository, clock=lambda: _NOW)

    saved = await service.update_state(older.event_id, saved=True, compare_later=True)
    ignored = await service.update_state(newer.event_id, ignored=True)
    saved_after_ignore = await service.update_state(older.event_id, ignored=True)

    assert saved.saved is True
    assert saved.compare_later is True
    assert ignored.ignored is True
    assert saved_after_ignore.saved is True
    assert saved_after_ignore.compare_later is True
    assert saved_after_ignore.ignored is True
    assert await service.list_items() == ()
    assert [
        item.event_id for item in await service.list_items(state_filter=JobInboxFilter.SAVED)
    ] == [older.event_id]
    assert {
        item.event_id for item in await service.list_items(state_filter=JobInboxFilter.IGNORED)
    } == {older.event_id, newer.event_id}
    assert [
        item.event_id
        for item in await service.list_items(state_filter=JobInboxFilter.COMPARE_LATER)
    ] == [older.event_id]
    assert [
        item.event_id
        for item in await service.list_items(
            kind=JobChangeKind.UPDATED,
            state_filter=JobInboxFilter.ALL,
        )
    ] == [newer.event_id]


@pytest.mark.asyncio
async def test_inbox_update_rejects_unknown_event() -> None:
    service = JobInboxService(InMemoryJobChangeRepository(), clock=lambda: _NOW)

    with pytest.raises(KeyError):
        await service.update_state(uuid4(), saved=True)
