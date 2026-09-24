from uuid import UUID

from lina_agent.application.agent_run_snapshot import AgentRunSnapshot
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentReference,
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
