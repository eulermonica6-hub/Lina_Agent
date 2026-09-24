from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from lina_agent.application.career_agent import (
    AgentRole,
    AgentRunState,
    AgentStepStatus,
    CareerAgentRun,
)
from lina_agent.domain.career_gap import CareerPlanReview, GapPriority
from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
)
from lina_agent.domain.career_planning import CareerActionPlan
from lina_agent.domain.models import DomainModel


class AgentRunRequestSnapshot(DomainModel):
    top_k: int = Field(ge=1, le=50)
    include_inactive: bool
    auto_decision_signals: bool
    candidate_availability: CandidateAvailabilityConfirmation | None = None
    candidate_direction_preferences: CandidateDirectionPreferenceConfirmation | None = None
    use_llm: bool


class AgentMatchSnapshot(DomainModel):
    catalog_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    score: float = Field(ge=0, le=100)
    skill_score: float = Field(ge=0, le=100)
    hard_compatibility: float | None = Field(default=None, ge=0, le=1)
    direction_alignment: float | None = Field(default=None, ge=0, le=1)
    matched_required_skills: tuple[str, ...] = ()
    missing_required_skills: tuple[str, ...] = ()
    matched_preferred_skills: tuple[str, ...] = ()
    missing_preferred_skills: tuple[str, ...] = ()


class AgentGapSnapshot(DomainModel):
    skill: str = Field(min_length=1)
    priority: GapPriority
    required_by_jobs: int = Field(ge=0)
    preferred_by_jobs: int = Field(ge=0)
    affected_catalog_numbers: tuple[int, ...] = Field(min_length=1)


class AgentStepSnapshot(DomainModel):
    name: str = Field(min_length=1)
    role: AgentRole
    status: AgentStepStatus


class AgentRunSnapshot(DomainModel):
    schema_version: Literal[1, 2] = 2
    run_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: AgentRunState
    candidate_document_id: UUID
    job_catalog_document_id: UUID
    candidate_document_reference_id: UUID | None = None
    job_catalog_document_reference_id: UUID | None = None
    candidate_confirmation_version_id: UUID | None = None
    total_jobs: int = Field(ge=0)
    considered_jobs: int = Field(ge=0)
    excluded_inactive_jobs: int = Field(ge=0)
    request: AgentRunRequestSnapshot
    matches: tuple[AgentMatchSnapshot, ...] = ()
    gaps: tuple[AgentGapSnapshot, ...] = ()
    action_plan: CareerActionPlan | None = None
    action_plan_review: CareerPlanReview | None = None
    steps: tuple[AgentStepSnapshot, ...] = Field(min_length=1)
    warning_count: int = Field(ge=0)


def create_agent_run_snapshot(
    run: CareerAgentRun,
    request: AgentRunRequestSnapshot,
    candidate_document_reference_id: UUID | None = None,
    job_catalog_document_reference_id: UUID | None = None,
    candidate_confirmation_version_id: UUID | None = None,
) -> AgentRunSnapshot:
    return AgentRunSnapshot(
        run_id=run.run_id,
        state=run.state,
        candidate_document_id=run.candidate.document_id,
        job_catalog_document_id=run.job_catalog_document_id,
        candidate_document_reference_id=candidate_document_reference_id,
        job_catalog_document_reference_id=job_catalog_document_reference_id,
        candidate_confirmation_version_id=candidate_confirmation_version_id,
        total_jobs=run.total_jobs,
        considered_jobs=run.considered_jobs,
        excluded_inactive_jobs=run.excluded_inactive_jobs,
        request=request,
        matches=tuple(
            AgentMatchSnapshot(
                catalog_number=match.catalog_number,
                title=match.title,
                company=match.company,
                score=match.score,
                skill_score=match.skill_score,
                hard_compatibility=match.hard_compatibility,
                direction_alignment=match.direction_alignment,
                matched_required_skills=tuple(item.skill for item in match.matched_required),
                missing_required_skills=tuple(item.skill for item in match.missing_required),
                matched_preferred_skills=tuple(item.skill for item in match.matched_preferred),
                missing_preferred_skills=tuple(item.skill for item in match.missing_preferred),
            )
            for match in run.matches
        ),
        gaps=tuple(
            AgentGapSnapshot(
                skill=gap.skill,
                priority=gap.priority,
                required_by_jobs=gap.required_by_jobs,
                preferred_by_jobs=gap.preferred_by_jobs,
                affected_catalog_numbers=gap.affected_catalog_numbers,
            )
            for gap in run.gap_analysis.gaps
        ),
        action_plan=run.action_plan,
        action_plan_review=run.action_plan_review,
        steps=tuple(
            AgentStepSnapshot(name=step.name, role=step.role, status=step.status)
            for step in run.steps
        ),
        warning_count=len(run.warnings),
    )
