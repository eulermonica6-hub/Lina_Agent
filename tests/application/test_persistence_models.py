import json

import pytest
from pydantic import ValidationError

from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentKind,
    create_confirmation_version,
    create_document_reference,
)
from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
)
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


def test_document_reference_separates_content_identity_from_role() -> None:
    document = LocalDocumentLoader().load_bytes("document.txt", b"Python")

    resume_reference = create_document_reference(
        document,
        DocumentKind.CANDIDATE_RESUME,
        byte_size=6,
    )
    catalog_reference = create_document_reference(
        document,
        DocumentKind.JOB_CATALOG,
        byte_size=6,
    )

    assert resume_reference.document_id == catalog_reference.document_id
    assert resume_reference.reference_id != catalog_reference.reference_id
    assert resume_reference.model_dump().keys().isdisjoint({"text", "source_name"})


def test_confirmation_versions_have_stable_fact_hash_and_unique_identity() -> None:
    availability = CandidateAvailabilityConfirmation(weekly_days=5, duration_months=12)
    preferences = CandidateDirectionPreferenceConfirmation(agent_llm_application=1)

    first = create_confirmation_version(availability, preferences)
    second = create_confirmation_version(availability, preferences)

    assert first is not None
    assert second is not None
    assert first.version_id != second.version_id
    assert first.facts_hash == second.facts_hash
    assert len(first.facts_hash) == 64
    assert json.loads(first.model_dump_json())["source"] == "user_confirmation"


def test_confirmation_factory_returns_none_without_facts() -> None:
    assert create_confirmation_version(None, None) is None


def test_confirmation_version_rejects_empty_facts() -> None:
    with pytest.raises(ValidationError, match="at least one fact"):
        CandidateConfirmationVersion(facts_hash="0" * 64)
