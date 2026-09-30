import hashlib
import json
from datetime import datetime

from lina_agent.application.repositories import JobChangeRepository
from lina_agent.domain.job_changes import (
    JobCaptureBatch,
    JobCaptureResult,
    JobChangeEvent,
    JobChangeKind,
    JobListingState,
)
from lina_agent.domain.job_discovery import JobLead


class JobChangeTrackingService:
    def __init__(self, repository: JobChangeRepository) -> None:
        self._repository = repository

    async def record_capture(
        self,
        source_id: str,
        leads: tuple[JobLead, ...],
        captured_at: datetime,
    ) -> JobCaptureResult:
        if any(lead.source_id != source_id for lead in leads):
            raise ValueError("All captured jobs must belong to the tracked source")
        current = {lead.external_id: lead for lead in leads}
        if len(current) != len(leads):
            raise ValueError("Captured jobs must have unique external IDs")

        previous_states = {
            state.external_id: state for state in await self._repository.list_states(source_id)
        }
        baseline = not await self._repository.list_batches(source_id)
        batch = JobCaptureBatch(
            source_id=source_id,
            captured_at=captured_at,
            job_count=len(current),
            baseline=baseline,
        )
        states: list[JobListingState] = []
        events: list[JobChangeEvent] = []

        for external_id, lead in current.items():
            previous = previous_states.get(external_id)
            fingerprint = lead.content_fingerprint or _lead_fingerprint(lead)
            state = JobListingState(
                source_id=source_id,
                external_id=external_id,
                title=lead.title,
                locations=lead.locations,
                job_type=lead.job_type,
                direction=lead.direction,
                source_url=lead.source_url,
                normalized_description=lead.normalized_description,
                content_fingerprint=fingerprint,
                first_seen_at=(previous.first_seen_at if previous is not None else captured_at),
                last_seen_at=captured_at,
                is_open=True,
            )
            states.append(state)
            kind = _event_kind(previous, fingerprint, baseline)
            if kind is not None:
                events.append(
                    JobChangeEvent(
                        batch_id=batch.batch_id,
                        source_id=source_id,
                        external_id=external_id,
                        kind=kind,
                        occurred_at=captured_at,
                        previous_fingerprint=(
                            previous.content_fingerprint if previous is not None else None
                        ),
                        current_fingerprint=fingerprint,
                        title=lead.title,
                        source_url=lead.source_url,
                    )
                )

        for external_id, previous in previous_states.items():
            if external_id in current:
                continue
            states.append(previous.model_copy(update={"is_open": False}))
            if previous.is_open:
                events.append(
                    JobChangeEvent(
                        batch_id=batch.batch_id,
                        source_id=source_id,
                        external_id=external_id,
                        kind=JobChangeKind.CLOSED,
                        occurred_at=captured_at,
                        previous_fingerprint=previous.content_fingerprint,
                        title=previous.title,
                        source_url=previous.source_url,
                    )
                )

        ordered_states = tuple(sorted(states, key=lambda state: state.state_key))
        ordered_events = tuple(sorted(events, key=lambda event: event.external_id))
        await self._repository.save_capture(batch, ordered_states, ordered_events)
        return JobCaptureResult(
            batch=batch,
            states=ordered_states,
            events=ordered_events,
        )


def _event_kind(
    previous: JobListingState | None,
    current_fingerprint: str,
    baseline: bool,
) -> JobChangeKind | None:
    if previous is None:
        return None if baseline else JobChangeKind.NEW
    if not previous.is_open:
        return JobChangeKind.REOPENED
    if previous.content_fingerprint != current_fingerprint:
        return JobChangeKind.UPDATED
    return None


def _lead_fingerprint(lead: JobLead) -> str:
    payload = json.dumps(
        {
            "title": lead.title,
            "locations": lead.locations,
            "job_type": lead.job_type,
            "direction": lead.direction,
            "source_url": lead.source_url,
            "description": lead.normalized_description,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
