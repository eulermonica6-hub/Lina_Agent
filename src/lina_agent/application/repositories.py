from typing import Protocol
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


class CandidateProfileRepository(Protocol):
    async def save(self, candidate: CandidateProfile) -> None: ...

    async def get(self, candidate_id: UUID) -> CandidateProfile | None: ...

    async def list_all(self) -> list[CandidateProfile]: ...


class JobPostingRepository(Protocol):
    async def save(self, job: JobPosting) -> None: ...

    async def get(self, job_id: UUID) -> JobPosting | None: ...

    async def list_all(self) -> list[JobPosting]: ...


class AgentRunSnapshotRepository(Protocol):
    async def save(self, snapshot: AgentRunSnapshot) -> None: ...

    async def get(self, run_id: UUID) -> AgentRunSnapshot | None: ...

    async def list_recent(self, limit: int) -> list[AgentRunSnapshot]: ...


class DocumentReferenceRepository(Protocol):
    async def save(self, reference: DocumentReference) -> None: ...

    async def get(self, reference_id: UUID) -> DocumentReference | None: ...


class CandidateConfirmationVersionRepository(Protocol):
    async def save(self, version: CandidateConfirmationVersion) -> None: ...

    async def get(self, version_id: UUID) -> CandidateConfirmationVersion | None: ...


class JobChangeRepository(Protocol):
    async def list_states(self, source_id: str) -> list[JobListingState]: ...

    async def save_capture(
        self,
        batch: JobCaptureBatch,
        states: tuple[JobListingState, ...],
        events: tuple[JobChangeEvent, ...],
    ) -> None: ...

    async def list_batches(self, source_id: str) -> list[JobCaptureBatch]: ...

    async def list_events(self, source_id: str | None = None) -> list[JobChangeEvent]: ...

    async def get_inbox_state(self, event_id: UUID) -> JobInboxState | None: ...

    async def save_inbox_state(self, state: JobInboxState) -> None: ...
