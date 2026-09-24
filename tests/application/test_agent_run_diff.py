from datetime import UTC, datetime
from uuid import UUID, uuid4

from lina_agent.application.agent_run_diff import create_agent_run_diff
from lina_agent.application.agent_run_snapshot import (
    AgentGapSnapshot,
    AgentMatchSnapshot,
    AgentRunRequestSnapshot,
    AgentRunSnapshot,
    AgentStepSnapshot,
)
from lina_agent.application.career_agent import AgentRole, AgentRunState, AgentStepStatus
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentKind,
    DocumentReference,
)
from lina_agent.domain.career_gap import GapPriority
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.domain.documents import DocumentFormat


def test_diff_reports_input_confirmation_ranking_score_and_gap_changes() -> None:
    candidate_reference = _reference(DocumentKind.CANDIDATE_RESUME, "a" * 64)
    base_catalog = _reference(DocumentKind.JOB_CATALOG, "b" * 64)
    target_catalog = _reference(DocumentKind.JOB_CATALOG, "c" * 64)
    base_confirmation = _confirmation("d" * 64)
    target_confirmation = _confirmation("e" * 64)
    base = _snapshot(
        candidate_reference.reference_id,
        base_catalog.reference_id,
        base_confirmation.version_id,
        matches=(
            AgentMatchSnapshot(
                catalog_number=1,
                title="One",
                company="A",
                score=80,
                skill_score=70,
            ),
            AgentMatchSnapshot(
                catalog_number=2,
                title="Two",
                company="B",
                score=60,
                skill_score=60,
            ),
        ),
        gaps=(
            AgentGapSnapshot(
                skill="PyTorch",
                priority=GapPriority.HIGH,
                required_by_jobs=1,
                preferred_by_jobs=0,
                affected_catalog_numbers=(1,),
            ),
        ),
    )
    target = _snapshot(
        candidate_reference.reference_id,
        target_catalog.reference_id,
        target_confirmation.version_id,
        matches=(
            AgentMatchSnapshot(
                catalog_number=2,
                title="Two",
                company="B",
                score=75,
                skill_score=75,
            ),
            AgentMatchSnapshot(
                catalog_number=1,
                title="One",
                company="A",
                score=65,
                skill_score=65,
            ),
        ),
        gaps=(
            AgentGapSnapshot(
                skill="CUDA",
                priority=GapPriority.HIGH,
                required_by_jobs=1,
                preferred_by_jobs=0,
                affected_catalog_numbers=(2,),
            ),
        ),
    )

    diff = create_agent_run_diff(
        base,
        target,
        base_candidate_document=candidate_reference,
        target_candidate_document=candidate_reference,
        base_job_catalog=base_catalog,
        target_job_catalog=target_catalog,
        base_confirmation=base_confirmation,
        target_confirmation=target_confirmation,
    )

    assert diff.candidate_document_changed is False
    assert diff.job_catalog_document_changed is True
    assert diff.confirmation_changed is True
    assert diff.base_ranking == (1, 2)
    assert diff.target_ranking == (2, 1)
    assert diff.ranking_changes[0].catalog_number == 2
    assert diff.ranking_changes[0].position_delta == -1
    assert diff.score_changes[0].score_delta == 15
    assert diff.added_gaps == ("CUDA",)
    assert diff.resolved_gaps == ("PyTorch",)


def test_diff_supports_version_one_snapshots_and_job_set_changes() -> None:
    base = _snapshot(
        None,
        None,
        None,
        matches=(
            AgentMatchSnapshot(
                catalog_number=1,
                title="One",
                company="A",
                score=80,
                skill_score=80,
            ),
        ),
        gaps=(),
    ).model_copy(update={"schema_version": 1})
    target = _snapshot(
        None,
        None,
        None,
        matches=(
            AgentMatchSnapshot(
                catalog_number=2,
                title="Two",
                company="B",
                score=70,
                skill_score=70,
            ),
        ),
        gaps=(),
    ).model_copy(
        update={
            "schema_version": 1,
            "candidate_document_id": base.candidate_document_id,
            "job_catalog_document_id": base.job_catalog_document_id,
        }
    )

    diff = create_agent_run_diff(base, target)

    assert diff.candidate_document_changed is False
    assert diff.job_catalog_document_changed is False
    assert diff.confirmation_changed is False
    assert diff.added_catalog_numbers == (2,)
    assert diff.removed_catalog_numbers == (1,)
    assert diff.ranking_changes == ()
    assert diff.score_changes == ()


def test_diff_marks_replaced_catalog_number_and_plan_change() -> None:
    base = _snapshot(
        None,
        None,
        None,
        matches=(
            AgentMatchSnapshot(
                catalog_number=1,
                title="Old",
                company="A",
                score=80,
                skill_score=80,
            ),
        ),
        gaps=(),
    )
    target = _snapshot(
        None,
        None,
        None,
        matches=(
            AgentMatchSnapshot(
                catalog_number=1,
                title="New",
                company="B",
                score=60,
                skill_score=60,
            ),
        ),
        gaps=(),
    ).model_copy(update={"action_plan": _plan()})

    diff = create_agent_run_diff(base, target)

    assert diff.replaced_catalog_numbers == (1,)
    assert diff.score_changes == ()
    assert diff.ranking_changes == ()
    assert diff.plan_changed is True


def _reference(kind: DocumentKind, content_hash: str) -> DocumentReference:
    return DocumentReference(
        reference_id=uuid4(),
        document_id=uuid4(),
        content_hash=content_hash,
        format=DocumentFormat.TEXT,
        kind=kind,
        byte_size=10,
        character_count=10,
        block_count=1,
    )


def _confirmation(facts_hash: str) -> CandidateConfirmationVersion:
    from lina_agent.domain.career_matching import CandidateAvailabilityConfirmation

    return CandidateConfirmationVersion(
        availability=CandidateAvailabilityConfirmation(weekly_days=5),
        facts_hash=facts_hash,
    )


def _snapshot(
    candidate_reference_id: UUID | None,
    catalog_reference_id: UUID | None,
    confirmation_version_id: UUID | None,
    *,
    matches: tuple[AgentMatchSnapshot, ...],
    gaps: tuple[AgentGapSnapshot, ...],
) -> AgentRunSnapshot:
    return AgentRunSnapshot(
        run_id=uuid4(),
        created_at=datetime(2026, 9, 24, tzinfo=UTC),
        state=AgentRunState.COMPLETE,
        candidate_document_id=uuid4(),
        job_catalog_document_id=uuid4(),
        candidate_document_reference_id=candidate_reference_id,
        job_catalog_document_reference_id=catalog_reference_id,
        candidate_confirmation_version_id=confirmation_version_id,
        total_jobs=len(matches),
        considered_jobs=len(matches),
        excluded_inactive_jobs=0,
        request=AgentRunRequestSnapshot(
            top_k=5,
            include_inactive=False,
            auto_decision_signals=True,
            use_llm=False,
        ),
        matches=matches,
        gaps=gaps,
        steps=(
            AgentStepSnapshot(
                name="rank_jobs",
                role=AgentRole.MATCHER,
                status=AgentStepStatus.COMPLETE,
            ),
        ),
        warning_count=0,
    )


def _plan() -> CareerActionPlan:
    return CareerActionPlan(
        summary="Build evidence",
        priority_actions=(
            CareerPlanAction(
                priority=1,
                target_skills=("Python",),
                action="Build project",
                reason="Required skill",
                deliverable="Repository",
                acceptance_criteria="Tests pass",
                time_budget_hours=4,
            ),
        ),
        provider="deterministic",
        model="test",
        total_tokens=0,
    )
