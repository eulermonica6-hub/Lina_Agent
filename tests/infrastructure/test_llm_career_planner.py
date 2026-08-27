import json

import pytest

from lina_agent.application.career_agent import CareerMatchAgent
from lina_agent.domain.career_gap import CareerGapAnalysis
from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.infrastructure.document_loader import LocalDocumentLoader
from lina_agent.infrastructure.llm_career_planner import CareerPlanningError, LLMCareerPlanner
from lina_agent.infrastructure.llm_provider import (
    LLMProviderName,
    LLMRequest,
    LLMResult,
    LLMUsage,
    ProviderRequestError,
)

JOBS = """### 1. Agent 工程师 | 甲公司
**岗位职责**
- 构建 Agent 与 RAG
**任职要求**
- Python
- LangGraph
"""


class _CapturingProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.request: LLMRequest | None = None

    def complete(self, request: LLMRequest) -> LLMResult:
        self.request = request
        return LLMResult(
            provider=LLMProviderName.GROQ,
            model="test-model",
            content=self.content,
            usage=LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


def _candidate_and_matches() -> tuple[
    CandidateDocumentProfile,
    tuple[RankedJobMatch, ...],
    CareerGapAnalysis,
]:
    loader = LocalDocumentLoader()
    resume = loader.load_bytes("private-resume.txt", "使用 Python 构建 RAG".encode())
    jobs = loader.load_bytes("jobs.md", JOBS.encode())
    run = CareerMatchAgent.execute_documents(resume, jobs)
    return run.candidate, run.matches, run.gap_analysis


def test_generates_schema_valid_plan_from_anonymized_structured_context() -> None:
    payload = {
        "summary": "先补齐编排证据",
        "priority_actions": [
            {
                "priority": 1,
                "target_skills": ["LangGraph"],
                "action": "完成 LangGraph 项目",
                "reason": "目标岗位明确要求",
                "deliverable": "可运行仓库",
                "acceptance_criteria": "三条工作流测试通过",
                "time_budget_hours": 12,
            }
        ],
        "interview_focus": ["解释 RAG 评测"],
    }
    provider = _CapturingProvider(f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```")
    candidate, matches, gap_analysis = _candidate_and_matches()

    plan = LLMCareerPlanner(provider).create_plan(candidate, matches, gap_analysis)

    assert plan.summary == "先补齐编排证据"
    assert plan.priority_actions[0].priority == 1
    assert plan.provider == "groq"
    assert plan.total_tokens == 30
    assert provider.request is not None
    assert provider.request.response_format == "json_object"
    assert provider.request.reasoning_effort == "none"
    context = json.loads(provider.request.messages[1].content)
    assert context["candidate_skills"] == ["RAG", "Python"]
    assert context["skill_gaps"][0]["skill"] == "LangGraph"
    assert context["top_jobs"][0]["missing_required"] == ["LangGraph"]
    serialized = provider.request.messages[1].content
    assert "private-resume.txt" not in serialized
    assert "使用 Python 构建 RAG" not in serialized


def test_rejects_non_json_or_schema_invalid_model_plan() -> None:
    candidate, matches, gap_analysis = _candidate_and_matches()

    with pytest.raises(CareerPlanningError, match="符合 Schema"):
        LLMCareerPlanner(_CapturingProvider("not json")).create_plan(
            candidate,
            matches,
            gap_analysis,
        )


def test_extracts_valid_plan_after_reasoning_text_and_schema_distractor() -> None:
    candidate, matches, gap_analysis = _candidate_and_matches()
    valid = {
        "summary": "补齐缺口",
        "priority_actions": [
            {
                "priority": 1,
                "target_skills": ["LangGraph"],
                "action": "实现状态图",
                "reason": "岗位偏好",
                "deliverable": "状态图 Demo",
                "acceptance_criteria": "三个节点测试通过",
                "time_budget_hours": 10,
            }
        ],
    }
    content = '<think>Schema: {"summary":"only"}</think>\nfinal:\n' + json.dumps(
        valid, ensure_ascii=False
    )

    plan = LLMCareerPlanner(_CapturingProvider(content)).create_plan(
        candidate,
        matches,
        gap_analysis,
    )

    assert plan.priority_actions[0].target_skills == ("LangGraph",)


class _UnavailableProvider:
    def complete(self, request: LLMRequest) -> LLMResult:
        raise ProviderRequestError("offline")


def test_wraps_provider_failure_as_degradable_planning_error() -> None:
    candidate, matches, gap_analysis = _candidate_and_matches()

    with pytest.raises(CareerPlanningError, match="保留确定性"):
        LLMCareerPlanner(_UnavailableProvider()).create_plan(
            candidate,
            matches,
            gap_analysis,
        )


def test_lazily_builds_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "summary": "构建证据",
        "priority_actions": [
            {
                "priority": 1,
                "target_skills": ["LangGraph"],
                "action": "完成项目",
                "reason": "岗位缺口",
                "deliverable": "仓库",
                "acceptance_criteria": "测试通过",
                "time_budget_hours": 8,
            }
        ],
    }
    provider = _CapturingProvider(json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(
        "lina_agent.infrastructure.llm_career_planner.build_economic_router",
        lambda: provider,
    )
    candidate, matches, gap_analysis = _candidate_and_matches()

    plan = LLMCareerPlanner().create_plan(candidate, matches, gap_analysis)

    assert plan.summary == "构建证据"
