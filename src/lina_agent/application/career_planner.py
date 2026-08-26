from typing import Protocol

from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan


class CareerPlanner(Protocol):
    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
    ) -> CareerActionPlan: ...
