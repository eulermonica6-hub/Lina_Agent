from pathlib import Path

import pytest

from lina_agent.application.career_agent import (
    AgentRunState,
    AgentStepStatus,
    CareerMatchAgent,
)
from lina_agent.application.career_planner import CareerPlannerError
from lina_agent.domain.career_gap import CareerGapAnalysis, PlanReviewStatus
from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
    CandidateDocumentProfile,
    DecisionSignals,
    DecisionWeights,
    RankedJobMatch,
)
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.infrastructure.document_loader import LocalDocumentLoader

ACTIVE_AND_INACTIVE_JOBS = """### 1. Agent 工程师 | 甲公司
**岗位职责**
- 开发 RAG Agent
**任职要求**
- 熟悉 Python
**状态与来源**
- 招聘中

### 2. Java 工程师 | 乙公司
**任职要求**
- 熟悉 Java
**状态与来源**
- 已下线
"""


class _FakePlanner:
    def __init__(self) -> None:
        self.calls = 0

    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan:
        self.calls += 1
        assert candidate.skills
        assert matches
        assert gap_analysis.analyzed_jobs == 1
        return CareerActionPlan(
            summary="测试计划",
            priority_actions=(
                CareerPlanAction(
                    priority=1,
                    target_skills=("Python",),
                    action="强化项目证据",
                    reason="岗位证据要求",
                    deliverable="项目说明",
                    acceptance_criteria="包含可复现步骤",
                    time_budget_hours=4,
                ),
            ),
            provider="groq",
            model="test-model",
            total_tokens=12,
        )


def test_executes_end_to_end_path_workflow_and_excludes_inactive_jobs(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.txt"
    jobs_path = tmp_path / "jobs.md"
    resume_path.write_text("Python 与 RAG 项目", encoding="utf-8")
    jobs_path.write_text(ACTIVE_AND_INACTIVE_JOBS, encoding="utf-8")

    run = CareerMatchAgent().execute_paths(resume_path, jobs_path, top_k=5)

    assert run.state is AgentRunState.COMPLETE
    assert run.total_jobs == 2
    assert run.considered_jobs == 1
    assert run.excluded_inactive_jobs == 1
    assert [match.catalog_number for match in run.matches] == [1]
    assert run.matches[0].score == 93.8
    assert run.matches[0].required_coverage == 1.0
    assert [step.name for step in run.steps] == [
        "ingest_resume",
        "ingest_job_catalog",
        "extract_candidate_facts",
        "parse_job_catalog",
        "rank_jobs",
        "analyze_skill_gaps",
    ]
    assert run.gap_analysis.analyzed_jobs == 1
    assert [strength.skill for strength in run.gap_analysis.strengths] == ["Python", "RAG"]
    assert any("排除了 1 个" in warning for warning in run.warnings)


def test_can_include_inactive_jobs_and_apply_top_k() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python Java")
    jobs = loader.load_bytes("jobs.md", ACTIVE_AND_INACTIVE_JOBS.encode())

    run = CareerMatchAgent.execute_documents(
        resume,
        jobs,
        top_k=1,
        include_inactive=True,
    )

    assert run.considered_jobs == 2
    assert run.excluded_inactive_jobs == 0
    assert len(run.matches) == 1
    assert not any("排除了" in warning for warning in run.warnings)


def test_can_rank_with_confirmed_hard_and_direction_signals() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    jobs = loader.load_bytes(
        "jobs.md",
        """### 1. Agent 岗位 | 甲公司
**任职要求**
- Python 与 LangGraph
### 2. 通用岗位 | 乙公司
**任职要求**
- Python
""".encode(),
    )

    run = CareerMatchAgent.execute_documents(
        resume,
        jobs,
        decision_signals={
            1: DecisionSignals(hard_compatibility=1, direction_alignment=1),
            2: DecisionSignals(hard_compatibility=1, direction_alignment=0),
        },
        decision_weights=DecisionWeights(skill=0.3, hard=0.2, direction=0.5),
    )

    assert [match.catalog_number for match in run.matches] == [1, 2]
    assert run.matches[0].skill_score == 50
    assert run.matches[0].score == 85
    assert any("已确认的硬条件与方向信号" in warning for warning in run.warnings)


def test_can_opt_in_to_evidence_backed_automatic_decision_signals() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes(
        "resume.txt",
        "2027 届硕士，期望地点上海。目标方向：AI Agent。熟悉 Python。".encode(),
    )
    jobs = loader.load_bytes(
        "jobs.md",
        """### 1. Agent 实习生 | 甲公司
**基本信息**
- 工作地点：上海
**任职要求**
- 2027 届本科及以上学历
- 熟悉 Python
**岗位职责**
- 开发 AI Agent
""".encode(),
    )

    run = CareerMatchAgent.execute_documents(
        resume,
        jobs,
        auto_decision_signals=True,
    )

    assert run.matches[0].score == 100
    assert run.matches[0].hard_compatibility == 1
    assert run.matches[0].direction_alignment == 1
    assert len(run.decision_signal_extractions) == 1
    assert any("自动抽取" in warning for warning in run.warnings)


def test_forwards_candidate_availability_to_automatic_signals() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    jobs = loader.load_bytes(
        "jobs.md",
        """### 1. 实习岗位 | 甲公司
**基本信息**
- 每周 4 天；连续 3 个月
**任职要求**
- Python
""".encode(),
    )

    run = CareerMatchAgent.execute_documents(
        resume,
        jobs,
        auto_decision_signals=True,
        candidate_availability=CandidateAvailabilityConfirmation(
            weekly_days=5,
            duration_months=2,
        ),
    )

    items = {item.name: item for item in run.decision_signal_extractions[0].hard_constraints}
    assert items["weekly_days"].status == "met"
    assert items["duration_months"].status == "unmet"
    assert items["weekly_days"].candidate_confirmation is not None
    assert items["weekly_days"].candidate_confirmation.source == "user_confirmation"


def test_rejects_candidate_availability_without_automatic_signals() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(ValueError, match="只能在自动决策信号开启时"):
        CareerMatchAgent.execute_documents(
            loader.load_bytes("resume.txt", b"Python"),
            loader.load_bytes("jobs.md", "### 1. 岗位 | 公司".encode()),
            candidate_availability=CandidateAvailabilityConfirmation(weekly_days=5),
        )


def test_forwards_candidate_direction_preferences_to_automatic_signals() -> None:
    loader = LocalDocumentLoader()
    run = CareerMatchAgent.execute_documents(
        loader.load_bytes("resume.txt", b"Python"),
        loader.load_bytes(
            "jobs.md",
            "### 1. AI Infra 实习岗位 | 甲公司\n**岗位职责**\n- 建设智能运维平台".encode(),
        ),
        auto_decision_signals=True,
        candidate_direction_preferences=CandidateDirectionPreferenceConfirmation(
            ai_infrastructure=0.8
        ),
    )

    direction = run.decision_signal_extractions[0].directions[0]
    assert run.matches[0].direction_alignment == 0.8
    assert direction.candidate_confirmation is not None
    assert direction.candidate_confirmation.source == "user_confirmation"


def test_rejects_candidate_direction_preferences_without_automatic_signals() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(ValueError, match="只能在自动决策信号开启时"):
        CareerMatchAgent.execute_documents(
            loader.load_bytes("resume.txt", b"Python"),
            loader.load_bytes("jobs.md", "### 1. 岗位 | 公司".encode()),
            candidate_direction_preferences=CandidateDirectionPreferenceConfirmation(
                ai_infrastructure=0.8
            ),
        )


def test_rejects_mixed_automatic_and_confirmed_decision_signals() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(ValueError, match="不能同时"):
        CareerMatchAgent.execute_documents(
            loader.load_bytes("resume.txt", b"Python"),
            loader.load_bytes("jobs.md", "### 1. 岗位 | 公司".encode()),
            decision_signals={1: DecisionSignals(hard_compatibility=1)},
            auto_decision_signals=True,
        )


def test_reports_empty_candidate_and_no_considered_jobs() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "善于沟通".encode())
    jobs = loader.load_bytes(
        "jobs.md",
        "### 1. Java 工程师 | 乙公司\n**状态与来源**\n- 已下线".encode(),
    )

    run = CareerMatchAgent.execute_documents(resume, jobs)

    assert run.matches == ()
    assert run.gap_analysis.analyzed_jobs == 0
    assert run.gap_analysis.gaps == ()
    assert any("未识别到技能词" in warning for warning in run.warnings)
    assert any("没有可参与排序" in warning for warning in run.warnings)


def test_rejects_invalid_top_k() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", b"Python")
    jobs = loader.load_bytes("jobs.md", "### 1. 岗位 | 公司".encode())

    with pytest.raises(ValueError, match="top_k"):
        CareerMatchAgent.execute_documents(resume, jobs, top_k=0)


def test_optional_planner_adds_action_plan_and_trace(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.txt"
    jobs_path = tmp_path / "jobs.md"
    resume_path.write_text("Python", encoding="utf-8")
    jobs_path.write_text(ACTIVE_AND_INACTIVE_JOBS, encoding="utf-8")
    planner = _FakePlanner()

    run = CareerMatchAgent(planner=planner).execute_paths(resume_path, jobs_path)

    assert planner.calls == 1
    assert run.action_plan is not None
    assert run.action_plan.summary == "测试计划"
    assert run.action_plan_review is not None
    assert run.action_plan_review.status is PlanReviewStatus.VERIFIED
    assert run.steps[-1].name == "verify_action_plan"


def test_optional_planner_is_skipped_without_ranked_jobs(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.txt"
    jobs_path = tmp_path / "jobs.md"
    resume_path.write_text("Python", encoding="utf-8")
    jobs_path.write_text(
        "### 1. 岗位 | 公司\n**状态与来源**\n- 已下线",
        encoding="utf-8",
    )
    planner = _FakePlanner()

    run = CareerMatchAgent(planner=planner).execute_paths(resume_path, jobs_path)

    assert planner.calls == 0
    assert run.action_plan is None
    assert run.steps[-1].status is AgentStepStatus.SKIPPED
    assert any("跳过智能行动计划" in warning for warning in run.warnings)


class _FailingPlanner:
    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan:
        raise CareerPlannerError("测试模型不可用")


class _UnsupportedSkillPlanner:
    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan:
        return CareerActionPlan(
            summary="包含无证据技能",
            priority_actions=(
                CareerPlanAction(
                    priority=1,
                    target_skills=("Kubernetes",),
                    action="部署集群",
                    reason="模型自行扩展",
                    deliverable="集群",
                    acceptance_criteria="可以访问",
                    time_budget_hours=8,
                ),
            ),
            provider="groq",
            model="test-model",
            total_tokens=10,
        )


@pytest.mark.parametrize(
    ("planner", "warning"),
    [
        (_FailingPlanner(), "测试模型不可用"),
        (_UnsupportedSkillPlanner(), "无证据技能"),
    ],
)
def test_planner_failure_or_rejection_degrades_without_losing_matches(
    tmp_path: Path,
    planner: _FailingPlanner | _UnsupportedSkillPlanner,
    warning: str,
) -> None:
    resume_path = tmp_path / "resume.txt"
    jobs_path = tmp_path / "jobs.md"
    resume_path.write_text("Python", encoding="utf-8")
    jobs_path.write_text(ACTIVE_AND_INACTIVE_JOBS, encoding="utf-8")

    run = CareerMatchAgent(planner=planner).execute_paths(resume_path, jobs_path)

    assert run.state is AgentRunState.DEGRADED
    assert run.matches
    assert run.action_plan is None
    assert run.steps[-1].status is AgentStepStatus.FAILED
    assert any(warning in item for item in run.warnings)
