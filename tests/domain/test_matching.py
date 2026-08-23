import pytest

from lina_agent.domain.matching import evaluate_hard_constraints
from lina_agent.domain.models import (
    CandidateProfile,
    EducationLevel,
    JobConstraints,
    JobPosting,
)


def make_candidate(
    *,
    graduation_year: int = 2027,
    education: EducationLevel = EducationLevel.BACHELOR,
    experience: float = 0,
    locations: set[str] | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        graduation_year=graduation_year,
        highest_education=education,
        years_of_experience=experience,
        preferred_locations=locations or {"北京", "上海"},
    )


def make_job(constraints: JobConstraints | None = None) -> JobPosting:
    return JobPosting(
        title="AI Agent Engineer",
        company="Example",
        description="Build reliable agent workflows.",
        constraints=constraints or JobConstraints(),
    )


@pytest.mark.parametrize(
    ("constraints", "candidate", "expected_reasons"),
    [
        (JobConstraints(), make_candidate(), ()),
        (JobConstraints(graduation_years={2027}), make_candidate(), ()),
        (
            JobConstraints(graduation_years={2026}),
            make_candidate(),
            ("graduation_year",),
        ),
        (
            JobConstraints(minimum_education=EducationLevel.BACHELOR),
            make_candidate(),
            (),
        ),
        (
            JobConstraints(minimum_education=EducationLevel.MASTER),
            make_candidate(),
            ("education",),
        ),
        (
            JobConstraints(minimum_years_of_experience=2),
            make_candidate(experience=1),
            ("experience",),
        ),
        (
            JobConstraints(locations={"深圳"}),
            make_candidate(locations={"上海"}),
            ("location",),
        ),
    ],
)
def test_evaluate_hard_constraints(
    constraints: JobConstraints,
    candidate: CandidateProfile,
    expected_reasons: tuple[str, ...],
) -> None:
    result = evaluate_hard_constraints(candidate, make_job(constraints))

    assert result.is_eligible is (not expected_reasons)
    assert result.reasons == expected_reasons


def test_evaluate_hard_constraints_returns_all_failures() -> None:
    candidate = make_candidate(
        education=EducationLevel.ASSOCIATE,
        experience=0,
        locations={"广州"},
    )
    job = make_job(
        JobConstraints(
            graduation_years={2026},
            minimum_education=EducationLevel.MASTER,
            minimum_years_of_experience=3,
            locations={"北京"},
        )
    )

    result = evaluate_hard_constraints(candidate, job)

    assert result.is_eligible is False
    assert result.reasons == (
        "graduation_year",
        "education",
        "experience",
        "location",
    )
