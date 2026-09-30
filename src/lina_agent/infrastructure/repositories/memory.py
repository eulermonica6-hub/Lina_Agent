from uuid import UUID

from lina_agent.application.agent_run_snapshot import AgentRunSnapshot
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentReference,
)
from lina_agent.domain.job_changes import (
    JobCaptureBatch,
    JobChangeEvent,
    JobInboxState,
    JobListingState,
)
from lina_agent.domain.models import CandidateProfile, JobPosting


class InMemoryCandidateProfileRepository:
    def __init__(self) -> None:
        self._candidates: dict[UUID, CandidateProfile] = {}

    async def save(self, candidate: CandidateProfile) -> None:
        self._candidates[candidate.id] = candidate.model_copy(deep=True)

    async def get(self, candidate_id: UUID) -> CandidateProfile | None:
        candidate = self._candidates.get(candidate_id)
        return candidate.model_copy(deep=True) if candidate is not None else None

    async def list_all(self) -> list[CandidateProfile]:
        return [candidate.model_copy(deep=True) for candidate in self._candidates.values()]


class InMemoryJobPostingRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, JobPosting] = {}

    async def save(self, job: JobPosting) -> None:
        self._jobs[job.id] = job.model_copy(deep=True)

    async def get(self, job_id: UUID) -> JobPosting | None:
        job = self._jobs.get(job_id)
        return job.model_copy(deep=True) if job is not None else None

    async def list_all(self) -> list[JobPosting]:
        return [job.model_copy(deep=True) for job in self._jobs.values()]


class InMemoryAgentRunSnapshotRepository:
    def __init__(self) -> None:
        self._snapshots: dict[UUID, AgentRunSnapshot] = {}

    async def save(self, snapshot: AgentRunSnapshot) -> None:
        self._snapshots[snapshot.run_id] = snapshot.model_copy(deep=True)

    async def get(self, run_id: UUID) -> AgentRunSnapshot | None:
        snapshot = self._snapshots.get(run_id)
        return snapshot.model_copy(deep=True) if snapshot is not None else None

    async def list_recent(self, limit: int) -> list[AgentRunSnapshot]:
        snapshots = sorted(
            self._snapshots.values(),
            key=lambda snapshot: snapshot.created_at,
            reverse=True,
        )[:limit]
        return [snapshot.model_copy(deep=True) for snapshot in snapshots]


class InMemoryDocumentReferenceRepository:
    def __init__(self) -> None:
        self._references: dict[UUID, DocumentReference] = {}

    async def save(self, reference: DocumentReference) -> None:
        self._references.setdefault(reference.reference_id, reference.model_copy(deep=True))

    async def get(self, reference_id: UUID) -> DocumentReference | None:
        reference = self._references.get(reference_id)
        return reference.model_copy(deep=True) if reference is not None else None


class InMemoryCandidateConfirmationVersionRepository:
    def __init__(self) -> None:
        self._versions: dict[UUID, CandidateConfirmationVersion] = {}

    async def save(self, version: CandidateConfirmationVersion) -> None:
        self._versions[version.version_id] = version.model_copy(deep=True)

    async def get(self, version_id: UUID) -> CandidateConfirmationVersion | None:
        version = self._versions.get(version_id)
        return version.model_copy(deep=True) if version is not None else None


class InMemoryJobChangeRepository:
    def __init__(self) -> None:
        self._states: dict[str, JobListingState] = {}
        self._batches: list[JobCaptureBatch] = []
        self._events: list[JobChangeEvent] = []
        self._inbox_states: dict[UUID, JobInboxState] = {}

    async def list_states(self, source_id: str) -> list[JobListingState]:
        return [
            state.model_copy(deep=True)
            for state in self._states.values()
            if state.source_id == source_id
        ]

    async def save_capture(
        self,
        batch: JobCaptureBatch,
        states: tuple[JobListingState, ...],
        events: tuple[JobChangeEvent, ...],
    ) -> None:
        self._batches.append(batch.model_copy(deep=True))
        for state in states:
            self._states[state.state_key] = state.model_copy(deep=True)
        self._events.extend(event.model_copy(deep=True) for event in events)

    async def list_batches(self, source_id: str) -> list[JobCaptureBatch]:
        return [
            batch.model_copy(deep=True) for batch in self._batches if batch.source_id == source_id
        ]

    async def list_events(self, source_id: str | None = None) -> list[JobChangeEvent]:
        return [
            event.model_copy(deep=True)
            for event in self._events
            if source_id is None or event.source_id == source_id
        ]

    async def get_inbox_state(self, event_id: UUID) -> JobInboxState | None:
        state = self._inbox_states.get(event_id)
        return state.model_copy(deep=True) if state is not None else None

    async def save_inbox_state(self, state: JobInboxState) -> None:
        self._inbox_states[state.event_id] = state.model_copy(deep=True)
