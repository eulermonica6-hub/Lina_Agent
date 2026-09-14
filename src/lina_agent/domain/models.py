from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EducationLevel(StrEnum):
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"


class DomainModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TextSpan(DomainModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_offset_range(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class SourceEvidence(TextSpan):
    document_id: UUID
    text: str = Field(min_length=1)


class CandidateProfile(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    graduation_year: int = Field(ge=1900, le=2200)
    highest_education: EducationLevel
    years_of_experience: float = Field(ge=0)
    skills: set[str] = Field(default_factory=set[str])
    preferred_locations: set[str] = Field(default_factory=set[str])


class JobConstraints(DomainModel):
    minimum_education: EducationLevel | None = None
    graduation_years: set[int] = Field(default_factory=set[int])
    minimum_years_of_experience: float | None = Field(default=None, ge=0)
    locations: set[str] = Field(default_factory=set[str])


class JobConstraintEvidence(DomainModel):
    graduation_years: tuple[SourceEvidence, ...] = ()
    minimum_education: SourceEvidence | None = None
    minimum_years_of_experience: SourceEvidence | None = None
    locations: tuple[SourceEvidence, ...] = ()


class JobConstraintExtraction(DomainModel):
    constraints: JobConstraints
    evidence: JobConstraintEvidence
    warnings: tuple[str, ...] = ()


class JobPosting(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    description: str = Field(min_length=1)
    constraints: JobConstraints = Field(default_factory=JobConstraints)
