from pathlib import Path

import pytest

from lina_agent.application.career_agent import AgentRunState, CareerMatchAgent
from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
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
    ) -> CareerActionPlan:
        self.calls += 1
        assert candidate.skills
        assert matches
        return CareerActionPlan(
            summary="测试计划",
            priority_actions=(
                CareerPlanAction(priority=1, action="补齐缺口", reason="岗位证据要求"),
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
    ]
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


def test_reports_empty_candidate_and_no_considered_jobs() -> None:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("resume.txt", "善于沟通".encode())
    jobs = loader.load_bytes(
        "jobs.md",
        "### 1. Java 工程师 | 乙公司\n**状态与来源**\n- 已下线".encode(),
    )

    run = CareerMatchAgent.execute_documents(resume, jobs)

    assert run.matches == ()
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
    assert run.steps[-1].name == "generate_action_plan"


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
    assert any("跳过智能行动计划" in warning for warning in run.warnings)
