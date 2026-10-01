from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from lina_agent.domain.models import DomainModel


class JobSourceStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    STRUCTURE_CHANGED = "structure_changed"
    FAILED = "failed"


class CompanyPool(StrEnum):
    ANCHOR = "anchor"
    DOMESTIC_MAJOR = "domestic_major"
    GLOBAL_MAJOR = "global_major"
    FOCUSED_AI = "focused_ai"


class JobType(StrEnum):
    INTERNSHIP = "internship"
    CAMPUS = "campus"
    FULL_TIME = "full_time"
    UNKNOWN = "unknown"


class JobVerificationStatus(StrEnum):
    LIVE = "live"
    NEEDS_REVERIFICATION = "needs_reverification"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class JobLead(DomainModel):
    lead_id: str = Field(min_length=1)
    deduplication_key: str = Field(min_length=1, exclude=True)
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    company_pool: CompanyPool = Field(default=CompanyPool.DOMESTIC_MAJOR, exclude=True)
    title: str = Field(min_length=1)
    job_type: JobType = JobType.UNKNOWN
    locations: tuple[str, ...]
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    captured_at: datetime
    verification_status: JobVerificationStatus
    highlights: tuple[str, ...] = ()
    normalized_description: str = Field(default="", exclude=True)
    content_fingerprint: str | None = Field(
        default=None,
        exclude=True,
        pattern=r"^[0-9a-f]{64}$",
    )

    @property
    def application_key(self) -> str:
        return f"{self.source_id}:{self.external_id}"


class JobSearchRequest(DomainModel):
    query: str | None = Field(default=None, min_length=1)
    companies: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    job_types: tuple[JobType, ...] = ()
    max_results: int = Field(default=50, ge=1, le=100)


class JobRecommendationRequest(DomainModel):
    preferred_companies: tuple[str, ...] = ()
    preferred_directions: tuple[str, ...] = ()
    recent_companies: tuple[str, ...] = ()
    preferred_locations: tuple[str, ...] = ()
    preferred_job_types: tuple[JobType, ...] = ()
    rotation_date: date | None = None
    week_start: date | None = None
    limit: int = Field(default=6, ge=1, le=9)


class JobSourceResult(DomainModel):
    source_id: str = Field(min_length=1)
    status: JobSourceStatus
    fetched_at: datetime
    leads: tuple[JobLead, ...] = ()
    error_code: str | None = None


class JobDiscoveryResult(DomainModel):
    sources: tuple[JobSourceResult, ...]
    leads: tuple[JobLead, ...]
