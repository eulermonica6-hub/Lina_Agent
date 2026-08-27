import base64

import pytest
from httpx import ASGITransport, AsyncClient

from lina_agent.api.routes import agent as agent_route
from lina_agent.domain.career_gap import CareerGapAnalysis
from lina_agent.domain.career_matching import CandidateDocumentProfile, RankedJobMatch
from lina_agent.domain.career_planning import CareerActionPlan, CareerPlanAction
from lina_agent.main import create_app


def _encoded(filename: str, text: str) -> dict[str, str]:
    return {
        "filename": filename,
        "content": base64.b64encode(text.encode()).decode("ascii"),
    }


@pytest.fixture
def agent_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_agent_api_runs_evidence_match_workflow(agent_client: AsyncClient) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python 与 RAG"),
        "job_catalog": _encoded(
            "jobs.md",
            "### 1. Agent 工程师 | 甲公司\n**任职要求**\n- Python\n- RAG 经验优先",
        ),
        "top_k": 1,
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "complete"
    assert payload["matches"][0]["score"] == 100
    assert payload["matches"][0]["matched_required"][0]["skill"] == "Python"
    assert payload["matches"][0]["matched_preferred"][0]["skill"] == "RAG"


@pytest.mark.asyncio
async def test_agent_api_returns_actionable_document_error(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.pdf", "not supported"),
        "job_catalog": _encoded("jobs.md", "普通文本"),
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 422
    assert "不支持的文档类型" in response.json()["detail"]


class _ApiPlanner:
    def create_plan(
        self,
        candidate: CandidateDocumentProfile,
        matches: tuple[RankedJobMatch, ...],
        gap_analysis: CareerGapAnalysis,
    ) -> CareerActionPlan:
        return CareerActionPlan(
            summary="API 智能计划",
            priority_actions=(
                CareerPlanAction(
                    priority=1,
                    target_skills=("Python",),
                    action="整理项目",
                    reason="证明岗位能力",
                    deliverable="项目仓库",
                    acceptance_criteria="测试通过",
                    time_budget_hours=4,
                ),
            ),
            provider="groq",
            model="test-model",
            total_tokens=15,
        )


@pytest.mark.asyncio
async def test_agent_api_can_explicitly_enable_llm_planning(
    agent_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_route, "LLMCareerPlanner", _ApiPlanner)
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded(
            "jobs.md",
            "### 1. Agent 工程师 | 甲公司\n**任职要求**\n- Python",
        ),
        "use_llm": True,
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["action_plan"]["summary"] == "API 智能计划"
    assert payload["action_plan_review"]["status"] == "verified"
