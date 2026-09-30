from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from lina_agent.domain.job_discovery import JobType
from lina_agent.domain.models import DomainModel


class JobChangeKind(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    CLOSED = "closed"
    REOPENED = "reopened"


class JobCaptureBatch(DomainModel):
    batch_id: UUID = Field(default_factory=uuid4)
    source_id: str = Field(min_length=1)
    captured_at: datetime
    job_count: int = Field(ge=0)
    baseline: bool = False


class JobListingState(DomainModel):
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    locations: tuple[str, ...]
    job_type: JobType
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    normalized_description: str = ""
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_seen_at: datetime
    last_seen_at: datetime
    is_open: bool = True

    @property
    def state_key(self) -> str:
        return f"{self.source_id}:{self.external_id}"


class JobChangeEvent(DomainModel):
    event_id: UUID = Field(default_factory=uuid4)
    batch_id: UUID
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    kind: JobChangeKind
    occurred_at: datetime
    previous_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    current_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")


class JobCaptureResult(DomainModel):
    batch: JobCaptureBatch
    states: tuple[JobListingState, ...]
    events: tuple[JobChangeEvent, ...]


class JobInboxState(DomainModel):
    event_id: UUID
    saved: bool = False
    ignored: bool = False
    compare_later: bool = False
    updated_at: datetime


class JobInboxItem(DomainModel):
    event_id: UUID
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    kind: JobChangeKind
    occurred_at: datetime
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    saved: bool = False
    ignored: bool = False
    compare_later: bool = False
