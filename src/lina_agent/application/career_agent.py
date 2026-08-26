from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field

from lina_agent.application.career_planner import CareerPlanner
from lina_agent.domain.career_matching import (
    CandidateDocumentProfile,
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


class AgentStep(DomainModel):
    name: str = Field(min_length=1)
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
    action_plan: CareerActionPlan | None = None
    steps: tuple[AgentStep, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class CareerMatchAgent:
    """A bounded supervisor with deterministic tools and an optional planning node."""

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
    ) -> CareerAgentRun:
        resume = self._loader.load(resume_path)
        job_catalog = self._loader.load(job_catalog_path)
        return self._execute_documents(
            resume,
            job_catalog,
            top_k=top_k,
            include_inactive=include_inactive,
            planner=self._planner,
        )

    @staticmethod
    def execute_documents(
        resume: IngestedDocument,
        job_catalog: IngestedDocument,
        *,
        top_k: int = 5,
        include_inactive: bool = False,
    ) -> CareerAgentRun:
        return CareerMatchAgent._execute_documents(
            resume,
            job_catalog,
            top_k=top_k,
            include_inactive=include_inactive,
            planner=None,
        )

    @staticmethod
    def _execute_documents(
        resume: IngestedDocument,
        job_catalog: IngestedDocument,
        *,
        top_k: int,
        include_inactive: bool,
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
                    score_job_match(candidate, job, extract_job_skill_profile(job))
                    for job in considered
                ),
                key=lambda match: (-match.score, match.catalog_number),
            )[:top_k]
        )

        warnings = [
            "首版分数表示已识别技能的证据覆盖度，不表示录取概率；学历、年限和毕业时间仍需人工确认。"
        ]
        if not candidate.skills:
            warnings.append("简历中未识别到技能词，请检查文档读取结果或扩展技能词表。")
        if excluded_count:
            warnings.append(f"默认排除了 {excluded_count} 个已下线或不可投递岗位。")
        if not considered:
            warnings.append("没有可参与排序的岗位。")

        action_plan = (
            planner.create_plan(candidate, ranked) if planner is not None and ranked else None
        )
        if planner is not None and not ranked:
            warnings.append("没有匹配结果，因此跳过智能行动计划。")

        steps = [
            AgentStep(
                name="ingest_resume",
                summary=f"从 {resume.source_name} 建立 {len(resume.blocks)} 个证据块。",
            ),
            AgentStep(
                name="ingest_job_catalog",
                summary=f"从 {job_catalog.source_name} 建立 {len(job_catalog.blocks)} 个证据块。",
            ),
            AgentStep(
                name="extract_candidate_facts",
                summary=f"识别 {len(candidate.skills)} 项候选人技能。",
            ),
            AgentStep(
                name="parse_job_catalog",
                summary=f"解析 {len(jobs)} 个岗位，{len(considered)} 个进入排序。",
            ),
            AgentStep(
                name="rank_jobs",
                summary=f"返回前 {len(ranked)} 个证据匹配结果。",
            ),
        ]
        if action_plan is not None:
            steps.append(
                AgentStep(
                    name="generate_action_plan",
                    summary=(
                        f"使用 {action_plan.provider}/{action_plan.model} 生成 "
                        f"{len(action_plan.priority_actions)} 项行动。"
                    ),
                )
            )

        return CareerAgentRun(
            state=AgentRunState.COMPLETE,
            candidate=candidate,
            job_catalog_document_id=job_catalog.id,
            total_jobs=len(jobs),
            considered_jobs=len(considered),
            excluded_inactive_jobs=excluded_count,
            matches=ranked,
            action_plan=action_plan,
            steps=tuple(steps),
            warnings=tuple(warnings),
        )
