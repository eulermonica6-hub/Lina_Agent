from uuid import uuid4

import pytest
from pydantic import ValidationError

from lina_agent.domain.models import CandidateProfile, EducationLevel, SourceEvidence


def test_candidate_profile_normalizes_collections() -> None:
    profile = CandidateProfile(
        graduation_year=2027,
        highest_education=EducationLevel.BACHELOR,
        years_of_experience=0,
        skills={" Python ", "Go"},
        preferred_locations={"北京"},
    )

    assert profile.skills == {"Python", "Go"}


def test_candidate_profile_rejects_negative_experience() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile(
            graduation_year=2027,
            highest_education=EducationLevel.BACHELOR,
            years_of_experience=-1,
        )


def test_source_evidence_requires_non_empty_text() -> None:
    with pytest.raises(ValidationError):
        SourceEvidence(
            document_id=uuid4(),
            text="",
            start_offset=0,
            end_offset=1,
        )


def test_source_evidence_rejects_non_increasing_offsets() -> None:
    with pytest.raises(ValidationError, match="end_offset must be greater than start_offset"):
        SourceEvidence(
            document_id=uuid4(),
            text="Python",
            start_offset=10,
            end_offset=4,
        )
