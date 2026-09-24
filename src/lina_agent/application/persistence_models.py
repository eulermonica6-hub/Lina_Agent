import json
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import Field, model_validator

from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
)
from lina_agent.domain.documents import DocumentFormat, IngestedDocument
from lina_agent.domain.models import DomainModel


class DocumentKind(StrEnum):
    CANDIDATE_RESUME = "candidate_resume"
    JOB_CATALOG = "job_catalog"


class DocumentSource(StrEnum):
    API_UPLOAD = "api_upload"


class DocumentRetentionPolicy(StrEnum):
    METADATA_ONLY = "metadata_only"


class DocumentReference(DomainModel):
    schema_version: Literal[1] = 1
    reference_id: UUID
    document_id: UUID
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: DocumentFormat
    kind: DocumentKind
    source: DocumentSource = DocumentSource.API_UPLOAD
    retention_policy: DocumentRetentionPolicy = DocumentRetentionPolicy.METADATA_ONLY
    byte_size: int = Field(ge=1)
    character_count: int = Field(ge=1)
    block_count: int = Field(ge=1)


class CandidateConfirmationVersion(DomainModel):
    schema_version: Literal[1] = 1
    version_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Literal["user_confirmation"] = "user_confirmation"
    availability: CandidateAvailabilityConfirmation | None = None
    direction_preferences: CandidateDirectionPreferenceConfirmation | None = None
    facts_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_has_confirmation(self) -> Self:
        if self.availability is None and self.direction_preferences is None:
            raise ValueError("confirmation version must contain at least one fact")
        return self


def create_document_reference(
    document: IngestedDocument,
    kind: DocumentKind,
    byte_size: int,
) -> DocumentReference:
    return DocumentReference(
        reference_id=uuid5(
            NAMESPACE_URL,
            f"lina-document-reference:{document.id}:{kind.value}",
        ),
        document_id=document.id,
        content_hash=document.content_hash,
        format=document.format,
        kind=kind,
        byte_size=byte_size,
        character_count=len(document.text),
        block_count=len(document.blocks),
    )


def create_confirmation_version(
    availability: CandidateAvailabilityConfirmation | None,
    direction_preferences: CandidateDirectionPreferenceConfirmation | None,
) -> CandidateConfirmationVersion | None:
    if availability is None and direction_preferences is None:
        return None
    payload = {
        "availability": (
            availability.model_dump(mode="json", exclude_none=True)
            if availability is not None
            else None
        ),
        "direction_preferences": (
            direction_preferences.model_dump(mode="json", exclude_none=True)
            if direction_preferences is not None
            else None
        ),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return CandidateConfirmationVersion(
        availability=availability,
        direction_preferences=direction_preferences,
        facts_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )
