from uuid import UUID

from lina_agent.application.errors import EntityNotFoundError
from lina_agent.application.repositories import (
    CandidateProfileRepository,
    JobPostingRepository,
)
from lina_agent.domain.matching import HardConstraintResult, evaluate_hard_constraints


class AnalyzeJobEligibility:
    def __init__(
        self,
        candidates: CandidateProfileRepository,
        jobs: JobPostingRepository,
    ) -> None:
        self._candidates = candidates
        self._jobs = jobs

    async def execute(self, candidate_id: UUID, job_id: UUID) -> HardConstraintResult:
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise EntityNotFoundError(f"candidate profile {candidate_id} was not found")

        job = await self._jobs.get(job_id)
        if job is None:
            raise EntityNotFoundError(f"job posting {job_id} was not found")

        return evaluate_hard_constraints(candidate, job)
