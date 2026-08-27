from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import Field

from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan
from lina_agent.domain.models import DomainModel, SourceEvidence


class GapPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SkillGap(DomainModel):
    skill: str = Field(min_length=1)
    required_by_jobs: int = Field(ge=0)
    preferred_by_jobs: int = Field(ge=0)
    affected_catalog_numbers: tuple[int, ...] = Field(min_length=1)
    priority_score: float = Field(ge=0, le=100)
    priority: GapPriority
    job_evidence: tuple[SourceEvidence, ...] = Field(min_length=1)


class SkillStrength(DomainModel):
    skill: str = Field(min_length=1)
    covered_jobs: int = Field(ge=1)
    catalog_numbers: tuple[int, ...] = Field(min_length=1)
    candidate_evidence: SourceEvidence


class CareerGapAnalysis(DomainModel):
    analyzed_jobs: int = Field(ge=0)
    gaps: tuple[SkillGap, ...] = ()
    strengths: tuple[SkillStrength, ...] = ()


class PlanReviewStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


class CareerPlanReview(DomainModel):
    status: PlanReviewStatus
    checked_actions: int = Field(ge=0)
    verified_target_skills: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


@dataclass
class _GapRecord:
    required: int = 0
    preferred: int = 0
    jobs: set[int] = field(default_factory=lambda: set[int]())
    evidence: list[SourceEvidence] = field(default_factory=lambda: list[SourceEvidence]())


@dataclass
class _StrengthRecord:
    evidence: SourceEvidence
    jobs: set[int] = field(default_factory=lambda: set[int]())


def analyze_career_gaps(matches: tuple[RankedJobMatch, ...]) -> CareerGapAnalysis:
    gap_records: dict[str, _GapRecord] = {}
    strength_records: dict[str, _StrengthRecord] = {}

    for match in matches:
        for mention in match.missing_required:
            record = gap_records.setdefault(mention.skill, _GapRecord())
            record.required += 1
            record.jobs.add(match.catalog_number)
            record.evidence.extend(mention.evidence)
        for mention in match.missing_preferred:
            record = gap_records.setdefault(mention.skill, _GapRecord())
            record.preferred += 1
            record.jobs.add(match.catalog_number)
            record.evidence.extend(mention.evidence)

        for evidence_match in (
            *match.matched_required,
            *match.matched_preferred,
            *match.matched_contextual,
        ):
            record = strength_records.setdefault(
                evidence_match.skill,
                _StrengthRecord(evidence=evidence_match.candidate_evidence),
            )
            record.jobs.add(match.catalog_number)

    analyzed_jobs = len(matches)
    gaps: list[SkillGap] = []
    for skill, record in gap_records.items():
        required = record.required
        preferred = record.preferred
        raw_score = (required + preferred * 0.35) / analyzed_jobs * 100
        priority_score = round(min(raw_score, 100), 1)
        if priority_score >= 66:
            priority = GapPriority.HIGH
        elif priority_score >= 33:
            priority = GapPriority.MEDIUM
        else:
            priority = GapPriority.LOW
        unique_evidence = tuple(
            {
                (item.document_id, item.start_offset, item.end_offset): item
                for item in record.evidence
            }.values()
        )
        gaps.append(
            SkillGap(
                skill=skill,
                required_by_jobs=required,
                preferred_by_jobs=preferred,
                affected_catalog_numbers=tuple(sorted(record.jobs)),
                priority_score=priority_score,
                priority=priority,
                job_evidence=unique_evidence,
            )
        )

    strengths: list[SkillStrength] = []
    for skill, record in strength_records.items():
        catalog_numbers = tuple(sorted(record.jobs))
        strengths.append(
            SkillStrength(
                skill=skill,
                covered_jobs=len(catalog_numbers),
                catalog_numbers=catalog_numbers,
                candidate_evidence=record.evidence,
            )
        )

    return CareerGapAnalysis(
        analyzed_jobs=analyzed_jobs,
        gaps=tuple(
            sorted(
                gaps,
                key=lambda item: (
                    -item.required_by_jobs,
                    -item.preferred_by_jobs,
                    item.skill,
                ),
            )
        ),
        strengths=tuple(sorted(strengths, key=lambda item: (-item.covered_jobs, item.skill))),
    )


def review_action_plan(
    plan: CareerActionPlan,
    candidate: CandidateDocumentProfile,
    gap_analysis: CareerGapAnalysis,
) -> CareerPlanReview:
    issues: list[str] = []
    priorities = [action.priority for action in plan.priority_actions]
    if priorities != list(range(1, len(priorities) + 1)):
        issues.append("行动优先级必须从 1 开始且连续。")

    action_names = [action.action.casefold() for action in plan.priority_actions]
    if len(action_names) != len(set(action_names)):
        issues.append("行动计划包含重复任务。")

    allowed_skills = {mention.skill for mention in candidate.skills} | {
        gap.skill for gap in gap_analysis.gaps
    }
    requested_skills = tuple(
        dict.fromkeys(skill for action in plan.priority_actions for skill in action.target_skills)
    )
    unknown_skills = tuple(skill for skill in requested_skills if skill not in allowed_skills)
    if unknown_skills:
        issues.append(f"行动计划引用了无证据技能：{'、'.join(unknown_skills)}。")

    return CareerPlanReview(
        status=(PlanReviewStatus.REJECTED if issues else PlanReviewStatus.VERIFIED),
        checked_actions=len(plan.priority_actions),
        verified_target_skills=tuple(
            skill for skill in requested_skills if skill in allowed_skills
        ),
        issues=tuple(issues),
    )
