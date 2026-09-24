import json
from uuid import UUID

from pydantic import Field

from lina_agent.application.agent_run_snapshot import AgentMatchSnapshot, AgentRunSnapshot
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentReference,
)
from lina_agent.domain.models import DomainModel


class RankingChange(DomainModel):
    catalog_number: int = Field(ge=1)
    base_position: int = Field(ge=1)
    target_position: int = Field(ge=1)
    position_delta: int


class ScoreChange(DomainModel):
    catalog_number: int = Field(ge=1)
    base_score: float = Field(ge=0, le=100)
    target_score: float = Field(ge=0, le=100)
    score_delta: float = Field(ge=-100, le=100)
    skill_score_delta: float = Field(ge=-100, le=100)
    hard_compatibility_changed: bool
    direction_alignment_changed: bool


class AgentRunDiff(DomainModel):
    base_run_id: UUID
    target_run_id: UUID
    candidate_document_changed: bool
    job_catalog_document_changed: bool
    confirmation_changed: bool
    state_changed: bool
    plan_changed: bool
    base_ranking: tuple[int, ...]
    target_ranking: tuple[int, ...]
    added_catalog_numbers: tuple[int, ...] = ()
    removed_catalog_numbers: tuple[int, ...] = ()
    replaced_catalog_numbers: tuple[int, ...] = ()
    ranking_changes: tuple[RankingChange, ...] = ()
    score_changes: tuple[ScoreChange, ...] = ()
    added_gaps: tuple[str, ...] = ()
    resolved_gaps: tuple[str, ...] = ()


def create_agent_run_diff(
    base: AgentRunSnapshot,
    target: AgentRunSnapshot,
    *,
    base_candidate_document: DocumentReference | None = None,
    target_candidate_document: DocumentReference | None = None,
    base_job_catalog: DocumentReference | None = None,
    target_job_catalog: DocumentReference | None = None,
    base_confirmation: CandidateConfirmationVersion | None = None,
    target_confirmation: CandidateConfirmationVersion | None = None,
) -> AgentRunDiff:
    base_matches = {match.catalog_number: match for match in base.matches}
    target_matches = {match.catalog_number: match for match in target.matches}
    base_numbers = set(base_matches)
    target_numbers = set(target_matches)
    shared_numbers = base_numbers & target_numbers
    replaced_numbers = {
        number
        for number in shared_numbers
        if (
            base_matches[number].title,
            base_matches[number].company,
        )
        != (
            target_matches[number].title,
            target_matches[number].company,
        )
    }
    common_numbers = shared_numbers - replaced_numbers
    base_ranking = tuple(match.catalog_number for match in base.matches)
    target_ranking = tuple(match.catalog_number for match in target.matches)
    base_positions = {number: index for index, number in enumerate(base_ranking, start=1)}
    target_positions = {number: index for index, number in enumerate(target_ranking, start=1)}
    ranking_changes = tuple(
        RankingChange(
            catalog_number=number,
            base_position=base_positions[number],
            target_position=target_positions[number],
            position_delta=target_positions[number] - base_positions[number],
        )
        for number in sorted(common_numbers, key=target_positions.__getitem__)
        if base_positions[number] != target_positions[number]
    )
    score_changes = tuple(
        sorted(
            (
                ScoreChange(
                    catalog_number=number,
                    base_score=base_matches[number].score,
                    target_score=target_matches[number].score,
                    score_delta=round(target_matches[number].score - base_matches[number].score, 3),
                    skill_score_delta=round(
                        target_matches[number].skill_score - base_matches[number].skill_score,
                        3,
                    ),
                    hard_compatibility_changed=(
                        base_matches[number].hard_compatibility
                        != target_matches[number].hard_compatibility
                    ),
                    direction_alignment_changed=(
                        base_matches[number].direction_alignment
                        != target_matches[number].direction_alignment
                    ),
                )
                for number in common_numbers
                if _match_changed(base_matches[number], target_matches[number])
            ),
            key=lambda item: (-abs(item.score_delta), -item.score_delta, item.catalog_number),
        )
    )
    base_gaps = {gap.skill for gap in base.gaps}
    target_gaps = {gap.skill for gap in target.gaps}
    return AgentRunDiff(
        base_run_id=base.run_id,
        target_run_id=target.run_id,
        candidate_document_changed=(
            _document_identity(base_candidate_document, base.candidate_document_id)
            != _document_identity(target_candidate_document, target.candidate_document_id)
        ),
        job_catalog_document_changed=(
            _document_identity(base_job_catalog, base.job_catalog_document_id)
            != _document_identity(target_job_catalog, target.job_catalog_document_id)
        ),
        confirmation_changed=(
            _confirmation_identity(base_confirmation, base)
            != _confirmation_identity(target_confirmation, target)
        ),
        state_changed=base.state != target.state,
        plan_changed=_normalized_plan(base) != _normalized_plan(target),
        base_ranking=base_ranking,
        target_ranking=target_ranking,
        added_catalog_numbers=tuple(sorted(target_numbers - base_numbers)),
        removed_catalog_numbers=tuple(sorted(base_numbers - target_numbers)),
        replaced_catalog_numbers=tuple(sorted(replaced_numbers)),
        ranking_changes=ranking_changes,
        score_changes=score_changes,
        added_gaps=tuple(sorted(target_gaps - base_gaps)),
        resolved_gaps=tuple(sorted(base_gaps - target_gaps)),
    )


def _document_identity(reference: DocumentReference | None, document_id: UUID) -> str:
    return reference.content_hash if reference is not None else str(document_id)


def _confirmation_identity(
    version: CandidateConfirmationVersion | None,
    snapshot: AgentRunSnapshot,
) -> str:
    if version is not None:
        return version.facts_hash
    payload = snapshot.request.model_dump(
        mode="json",
        include={"candidate_availability", "candidate_direction_preferences"},
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _normalized_plan(snapshot: AgentRunSnapshot) -> str | None:
    return (
        snapshot.action_plan.model_dump_json(exclude={"provider", "model", "total_tokens"})
        if snapshot.action_plan is not None
        else None
    )


def _match_changed(base_match: AgentMatchSnapshot, target_match: AgentMatchSnapshot) -> bool:
    return any(
        (
            base_match.score != target_match.score,
            base_match.skill_score != target_match.skill_score,
            base_match.hard_compatibility != target_match.hard_compatibility,
            base_match.direction_alignment != target_match.direction_alignment,
        )
    )
