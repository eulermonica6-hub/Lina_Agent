from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lina_agent.domain.models import CandidateProfile, EducationLevel, JobPosting


class HardConstraintFailure(StrEnum):
    GRADUATION_YEAR = "graduation_year"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    LOCATION = "location"


class HardConstraintResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_eligible: bool
    reasons: tuple[HardConstraintFailure, ...]


_EDUCATION_RANK = {
    EducationLevel.HIGH_SCHOOL: 0,
    EducationLevel.ASSOCIATE: 1,
    EducationLevel.BACHELOR: 2,
    EducationLevel.MASTER: 3,
    EducationLevel.DOCTORATE: 4,
}


def evaluate_hard_constraints(
    candidate: CandidateProfile,
    job: JobPosting,
) -> HardConstraintResult:
    constraints = job.constraints
    reasons: list[HardConstraintFailure] = []

    if (
        constraints.graduation_years
        and candidate.graduation_year not in constraints.graduation_years
    ):
        reasons.append(HardConstraintFailure.GRADUATION_YEAR)

    if (
        constraints.minimum_education is not None
        and _EDUCATION_RANK[candidate.highest_education]
        < _EDUCATION_RANK[constraints.minimum_education]
    ):
        reasons.append(HardConstraintFailure.EDUCATION)

    if (
        constraints.minimum_years_of_experience is not None
        and candidate.years_of_experience < constraints.minimum_years_of_experience
    ):
        reasons.append(HardConstraintFailure.EXPERIENCE)

    if constraints.locations and constraints.locations.isdisjoint(candidate.preferred_locations):
        reasons.append(HardConstraintFailure.LOCATION)

    return HardConstraintResult(is_eligible=not reasons, reasons=tuple(reasons))
