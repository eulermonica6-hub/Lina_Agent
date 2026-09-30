from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from lina_agent.application.repositories import JobChangeRepository
from lina_agent.domain.job_changes import (
    JobChangeEvent,
    JobChangeKind,
    JobInboxItem,
    JobInboxState,
)


class JobInboxFilter(StrEnum):
    UNHANDLED = "unhandled"
    SAVED = "saved"
    IGNORED = "ignored"
    COMPARE_LATER = "compare_later"
    ALL = "all"


class JobInboxService:
    def __init__(
        self,
        repository: JobChangeRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    async def list_items(
        self,
        *,
        kind: JobChangeKind | None = None,
        state_filter: JobInboxFilter = JobInboxFilter.UNHANDLED,
    ) -> tuple[JobInboxItem, ...]:
        events = await self._repository.list_events()
        items: list[JobInboxItem] = []
        for event in events:
            state = await self._repository.get_inbox_state(event.event_id)
            item = _to_item(event, state)
            if (kind is None or item.kind is kind) and _matches_filter(
                item,
                state_filter,
            ):
                items.append(item)
        return tuple(sorted(items, key=lambda item: item.occurred_at, reverse=True))

    async def update_state(
        self,
        event_id: UUID,
        *,
        saved: bool | None = None,
        ignored: bool | None = None,
        compare_later: bool | None = None,
    ) -> JobInboxItem:
        event = next(
            (
                candidate
                for candidate in await self._repository.list_events()
                if candidate.event_id == event_id
            ),
            None,
        )
        if event is None:
            raise KeyError(event_id)
        current = await self._repository.get_inbox_state(event_id)
        state = JobInboxState(
            event_id=event_id,
            saved=saved if saved is not None else current.saved if current else False,
            ignored=(ignored if ignored is not None else current.ignored if current else False),
            compare_later=(
                compare_later
                if compare_later is not None
                else current.compare_later
                if current
                else False
            ),
            updated_at=self._clock(),
        )
        await self._repository.save_inbox_state(state)
        return _to_item(event, state)


def _to_item(event: JobChangeEvent, state: JobInboxState | None) -> JobInboxItem:
    return JobInboxItem(
        event_id=event.event_id,
        source_id=event.source_id,
        external_id=event.external_id,
        kind=event.kind,
        occurred_at=event.occurred_at,
        title=event.title,
        source_url=event.source_url,
        saved=state.saved if state is not None else False,
        ignored=state.ignored if state is not None else False,
        compare_later=state.compare_later if state is not None else False,
    )


def _matches_filter(item: JobInboxItem, state_filter: JobInboxFilter) -> bool:
    if state_filter is JobInboxFilter.ALL:
        return True
    if state_filter is JobInboxFilter.SAVED:
        return item.saved
    if state_filter is JobInboxFilter.IGNORED:
        return item.ignored
    if state_filter is JobInboxFilter.COMPARE_LATER:
        return item.compare_later
    return not item.saved and not item.ignored and not item.compare_later
