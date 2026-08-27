from typing import Protocol

from lina_agent.domain.career_gap import CareerGapAnalysis
from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan


class CareerPlannerError(RuntimeError):
    """Raised when an optional planning node cannot produce an acceptable plan."""


class CareerPlanner(Protocol):
    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan: ...
