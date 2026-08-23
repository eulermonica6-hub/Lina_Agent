from typing import Protocol
from uuid import UUID

from lina_agent.domain.models import CandidateProfile, JobPosting


class CandidateProfileRepository(Protocol):
    async def save(self, candidate: CandidateProfile) -> None: ...

    async def get(self, candidate_id: UUID) -> CandidateProfile | None: ...

    async def list_all(self) -> list[CandidateProfile]: ...


class JobPostingRepository(Protocol):
    async def save(self, job: JobPosting) -> None: ...

    async def get(self, job_id: UUID) -> JobPosting | None: ...

    async def list_all(self) -> list[JobPosting]: ...
