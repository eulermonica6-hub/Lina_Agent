from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field

from lina_agent.application.career_planner import CareerPlanner, CareerPlannerError
from lina_agent.domain.career_gap import (
    CareerGapAnalysis,
    CareerPlanReview,
    PlanReviewStatus,
    analyze_career_gaps,
    review_action_plan,
)
from lina_agent.domain.career_matching import (
    CandidateDocumentProfile,
    DecisionSignals,
    DecisionWeights,
    RankedJobMatch,
    extract_candidate_profile,
    extract_job_skill_profile,
    score_job_match,
)
from lina_agent.domain.career_planning import CareerActionPlan
from lina_agent.domain.documents import IngestedDocument
from lina_agent.domain.job_catalog import parse_job_catalog
from lina_agent.domain.models import DomainModel
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


class AgentRunState(StrEnum):
    COMPLETE = "complete"
    DEGRADED = "degraded"


class AgentStepStatus(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentRole(StrEnum):
    DOCUMENT_INGESTOR = "document_ingestor"
    CANDIDATE_ANALYST = "candidate_analyst"
    JOB_ANALYST = "job_analyst"
    MATCHER = "matcher"
    GAP_ANALYST = "gap_analyst"
    CAREER_PLANNER = "career_planner"
    PLAN_REVIEWER = "plan_reviewer"


class AgentStep(DomainModel):
    name: str = Field(min_length=1)
    role: AgentRole
    status: AgentStepStatus = AgentStepStatus.COMPLETE
    summary: str = Field(min_length=1)


class CareerAgentRun(DomainModel):
    run_id: UUID = Field(default_factory=uuid4)
    state: AgentRunState
    candidate: CandidateDocumentProfile
    job_catalog_document_id: UUID
    total_jobs: int = Field(ge=0)
    considered_jobs: int = Field(ge=0)
    excluded_inactive_jobs: int = Field(ge=0)
    matches: tuple[RankedJobMatch, ...] = ()
    gap_analysis: CareerGapAnalysis
    action_plan: CareerActionPlan | None = None
    action_plan_review: CareerPlanReview | None = None
    steps: tuple[AgentStep, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class CareerMatchAgent:
    """A bounded supervisor for deterministic specialists and an optional LLM planner."""

    def __init__(
        self,
        loader: LocalDocumentLoader | None = None,
        planner: CareerPlanner | None = None,
    ) -> None:
        self._loader = loader or LocalDocumentLoader()
        self._planner = planner

    def execute_paths(
        self,
        resume_path: Path,
        job_catalog_path: Path,
        *,
        top_k: int = 5,
        include_inactive: bool = False,
        decision_signals: Mapping[int, DecisionSignals] | None = None,
        decision_weights: DecisionWeights | None = None,
    ) -> CareerAgentRun:
        resume = self._loader.load(resume_path)
        job_catalog = self._loader.load(job_catalog_path)
        return self._execute_documents(
            resume,
            job_catalog,
            top_k=top_k,
            include_inactive=include_inactive,
            decision_signals=decision_signals,
            decision_weights=decision_weights,
            planner=self._planner,
        )

    @staticmethod
    def execute_documents(
        resume: IngestedDocument,
        job_catalog: IngestedDocument,
        *,
        top_k: int = 5,
        include_inactive: bool = False,
        decision_signals: Mapping[int, DecisionSignals] | None = None,
        decision_weights: DecisionWeights | None = None,
        planner: CareerPlanner | None = None,
    ) -> CareerAgentRun:
        return CareerMatchAgent._execute_documents(
            resume,
            job_catalog,
            top_k=top_k,
            include_inactive=include_inactive,
            decision_signals=decision_signals,
            decision_weights=decision_weights,
            planner=planner,
        )

    @staticmethod
    def _execute_documents(
        resume: IngestedDocument,
        job_catalog: IngestedDocument,
        *,
        top_k: int,
        include_inactive: bool,
        decision_signals: Mapping[int, DecisionSignals] | None,
        decision_weights: DecisionWeights | None,
        planner: CareerPlanner | None,
    ) -> CareerAgentRun:
        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")

        candidate = extract_candidate_profile(resume)
        jobs = parse_job_catalog(job_catalog)
        considered = tuple(job for job in jobs if include_inactive or job.is_active is not False)
        excluded_count = len(jobs) - len(considered)
        ranked = tuple(
            sorted(
                (
                    score_job_match(
                        candidate,
                        job,
                        extract_job_skill_profile(job),
                        decision_signals=(
                            decision_signals.get(job.catalog_number)
                            if decision_signals is not None
                            else None
                        ),
                        decision_weights=decision_weights,
                    )
                    for job in considered
                ),
                key=lambda match: (-match.score, match.catalog_number),
            )[:top_k]
        )

        warnings = [
            (
                "综合分使用已确认的硬条件与方向信号，不表示录取概率。"
                if decision_signals is not None
                else (
                    "首版分数表示已识别技能的证据覆盖度，不表示录取概率；"
                    "学历、年限和毕业时间仍需人工确认。"
                )
            )
        ]
        if not candidate.skills:
            warnings.append("简历中未识别到技能词，请检查文档读取结果或扩展技能词表。")
        if excluded_count:
            warnings.append(f"默认排除了 {excluded_count} 个已下线或不可投递岗位。")
        if not considered:
            warnings.append("没有可参与排序的岗位。")

        gap_analysis = analyze_career_gaps(ranked)
        steps = [
            AgentStep(
                name="ingest_resume",
                role=AgentRole.DOCUMENT_INGESTOR,
                summary=f"从 {resume.source_name} 建立 {len(resume.blocks)} 个证据块。",
            ),
            AgentStep(
                name="ingest_job_catalog",
                role=AgentRole.DOCUMENT_INGESTOR,
                summary=f"从 {job_catalog.source_name} 建立 {len(job_catalog.blocks)} 个证据块。",
            ),
            AgentStep(
                name="extract_candidate_facts",
                role=AgentRole.CANDIDATE_ANALYST,
                summary=f"识别 {len(candidate.skills)} 项候选人技能。",
            ),
            AgentStep(
                name="parse_job_catalog",
                role=AgentRole.JOB_ANALYST,
                summary=f"解析 {len(jobs)} 个岗位，{len(considered)} 个进入排序。",
            ),
            AgentStep(
                name="rank_jobs",
                role=AgentRole.MATCHER,
                summary=f"返回前 {len(ranked)} 个证据匹配结果。",
            ),
            AgentStep(
                name="analyze_skill_gaps",
                role=AgentRole.GAP_ANALYST,
                summary=(
                    f"聚合 {gap_analysis.analyzed_jobs} 个岗位，识别 "
                    f"{len(gap_analysis.gaps)} 项能力缺口与 "
                    f"{len(gap_analysis.strengths)} 项证据优势。"
                ),
            ),
        ]

        state = AgentRunState.COMPLETE
        action_plan: CareerActionPlan | None = None
        action_plan_review: CareerPlanReview | None = None
        if planner is not None and ranked:
            try:
                generated_plan = planner.create_plan(candidate, ranked, gap_analysis)
            except CareerPlannerError as error:
                state = AgentRunState.DEGRADED
                warnings.append(f"智能行动计划已降级：{error}")
                steps.append(
                    AgentStep(
                        name="generate_action_plan",
                        role=AgentRole.CAREER_PLANNER,
                        status=AgentStepStatus.FAILED,
                        summary="模型计划节点失败，确定性匹配与缺口分析仍然可用。",
                    )
                )
            else:
                steps.append(
                    AgentStep(
                        name="generate_action_plan",
                        role=AgentRole.CAREER_PLANNER,
                        summary=(
                            f"使用 {generated_plan.provider}/{generated_plan.model} 生成 "
                            f"{len(generated_plan.priority_actions)} 项行动。"
                        ),
                    )
                )
                action_plan_review = review_action_plan(
                    generated_plan,
                    candidate,
                    gap_analysis,
                )
                if action_plan_review.status is PlanReviewStatus.VERIFIED:
                    action_plan = generated_plan
                    steps.append(
                        AgentStep(
                            name="verify_action_plan",
                            role=AgentRole.PLAN_REVIEWER,
                            summary=(
                                f"验证 {action_plan_review.checked_actions} 项行动和 "
                                f"{len(action_plan_review.verified_target_skills)} 项目标技能。"
                            ),
                        )
                    )
                else:
                    state = AgentRunState.DEGRADED
                    warnings.extend(action_plan_review.issues)
                    steps.append(
                        AgentStep(
                            name="verify_action_plan",
                            role=AgentRole.PLAN_REVIEWER,
                            status=AgentStepStatus.FAILED,
                            summary="模型计划未通过确定性证据复核，已拒绝进入正式结果。",
                        )
                    )
        elif planner is not None:
            warnings.append("没有匹配结果，因此跳过智能行动计划。")
            steps.append(
                AgentStep(
                    name="generate_action_plan",
                    role=AgentRole.CAREER_PLANNER,
                    status=AgentStepStatus.SKIPPED,
                    summary="没有匹配结果，未调用模型计划节点。",
                )
            )

        return CareerAgentRun(
            state=state,
            candidate=candidate,
            job_catalog_document_id=job_catalog.id,
            total_jobs=len(jobs),
            considered_jobs=len(considered),
            excluded_inactive_jobs=excluded_count,
            matches=ranked,
            gap_analysis=gap_analysis,
            action_plan=action_plan,
            action_plan_review=action_plan_review,
            steps=tuple(steps),
            warnings=tuple(warnings),
        )
