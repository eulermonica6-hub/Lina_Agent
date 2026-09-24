from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import Field

from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
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


@dataclass(frozen=True)
class _SkillEvidenceRecipe:
    rank: int
    action: str
    deliverable: str
    acceptance_criteria: str
    time_budget_hours: int


_SKILL_EVIDENCE_RECIPES = {
    "PyTorch": _SkillEvidenceRecipe(
        rank=1,
        action="实现并分析一个 PyTorch LLM 推理基线",
        deliverable="可复现的 PyTorch 推理仓库与性能报告",
        acceptance_criteria="固定输入下测试通过，并记录吞吐、延迟、显存和优化前后对比",
        time_budget_hours=16,
    ),
    "C++": _SkillEvidenceRecipe(
        rank=2,
        action="实现 C++ 推理算子并接入 Python 基线",
        deliverable="带 Python 绑定、单元测试和构建脚本的 C++ 扩展",
        acceptance_criteria="一条命令完成构建和测试，输出与 PyTorch 参考实现误差在阈值内",
        time_budget_hours=20,
    ),
    "CUDA": _SkillEvidenceRecipe(
        rank=3,
        action="实现并优化一个 CUDA 推理内核",
        deliverable="CUDA Kernel、正确性测试和可复现实验记录",
        acceptance_criteria="与参考实现结果一致，并用基准报告说明优化前后性能和瓶颈",
        time_budget_hours=24,
    ),
}


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


def build_skill_evidence_plan(target_match: RankedJobMatch) -> CareerActionPlan:
    missing_skills = tuple(dict.fromkeys(item.skill for item in target_match.missing_required))
    selected_skills = tuple(
        sorted(
            missing_skills,
            key=lambda skill: (
                _SKILL_EVIDENCE_RECIPES.get(
                    skill,
                    _SkillEvidenceRecipe(99, "", "", "", 8),
                ).rank,
                skill,
            ),
        )[:3]
    )
    actions = tuple(
        _skill_evidence_action(priority, skill)
        for priority, skill in enumerate(selected_skills, start=1)
    )
    if not actions:
        raise ValueError("目标岗位没有待补齐的 required 技能证据")
    return CareerActionPlan(
        summary=f"为 {target_match.title} 补齐可复现的 required 技能证据。",
        priority_actions=actions,
        interview_focus=tuple(
            f"说明 {skill} 的实现取舍、测量方法和失败复盘" for skill in selected_skills
        ),
        provider="deterministic",
        model="skill-evidence-v1",
        total_tokens=0,
    )


def _skill_evidence_action(priority: int, skill: str) -> CareerPlanAction:
    recipe = _SKILL_EVIDENCE_RECIPES.get(
        skill,
        _SkillEvidenceRecipe(
            rank=99,
            action=f"完成一个可运行的 {skill} 最小项目",
            deliverable=f"包含测试、README 和运行示例的 {skill} 仓库",
            acceptance_criteria="一条命令运行测试与示例，并记录关键设计选择和失败案例",
            time_budget_hours=8,
        ),
    )
    return CareerPlanAction(
        priority=priority,
        target_skills=(skill,),
        action=recipe.action,
        reason=f"目标岗位将 {skill} 列为 required，但当前简历没有直接证据。",
        deliverable=recipe.deliverable,
        acceptance_criteria=recipe.acceptance_criteria,
        time_budget_hours=recipe.time_budget_hours,
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
