import base64
import hashlib
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from lina_agent.api.routes import agent as agent_route
from lina_agent.config import Settings
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
    app = create_app(Settings(app_name="Lina Test", environment="test"))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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
async def test_agent_run_snapshot_survives_restart_without_raw_document_text(
    tmp_path: Path,
) -> None:
    settings = Settings(environment="development", database_path=tmp_path / "lina.db")
    request = {
        "resume": _encoded("private-person-name.txt", "Python PRIVATE_RESUME_SENTINEL"),
        "job_catalog": _encoded(
            "private-company-jobs.md",
            """### 1. Agent 实习生 | [COMPANY_A]
**岗位职责**
- PRIVATE_JOB_SENTINEL
**任职要求**
- Python
""",
        ),
        "top_k": 1,
        "auto_decision_signals": True,
        "candidate_direction_preferences": {"agent_llm_application": 1.0},
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)),
        base_url="http://test",
    ) as client:
        create_response = await client.post("/agent/runs", json=request)

    run_id = create_response.json()["run_id"]
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/agent/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 2
    assert payload["run_id"] == run_id
    assert payload["matches"][0]["matched_required_skills"] == ["Python"]
    assert payload["request"]["candidate_direction_preferences"]["agent_llm_application"] == 1
    confirmation_version_id = payload["candidate_confirmation_version_id"]
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)),
        base_url="http://test",
    ) as client:
        resume_reference = await client.get(
            f"/agent/documents/{payload['candidate_document_reference_id']}"
        )
        catalog_reference = await client.get(
            f"/agent/documents/{payload['job_catalog_document_reference_id']}"
        )
        confirmation = await client.get(f"/agent/confirmations/{confirmation_version_id}")

    assert resume_reference.status_code == 200
    assert (
        resume_reference.json()["content_hash"]
        == hashlib.sha256(b"Python PRIVATE_RESUME_SENTINEL").hexdigest()
    )
    assert resume_reference.json()["kind"] == "candidate_resume"
    assert resume_reference.json()["retention_policy"] == "metadata_only"
    assert catalog_reference.status_code == 200
    assert catalog_reference.json()["kind"] == "job_catalog"
    assert confirmation.status_code == 200
    assert confirmation.json()["direction_preferences"]["agent_llm_application"] == 1
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "PRIVATE_RESUME_SENTINEL" not in serialized
    assert "PRIVATE_JOB_SENTINEL" not in serialized
    assert "private-person-name.txt" not in serialized
    assert "private-company-jobs.md" not in serialized
    assert "start_offset" not in serialized
    assert "end_offset" not in serialized
    assert "private-person-name.txt" not in json.dumps(resume_reference.json())


@pytest.mark.asyncio
async def test_agent_run_snapshot_list_is_recent_first_and_bounded(
    agent_client: AsyncClient,
) -> None:
    requests = (
        {
            "resume": _encoded("first.txt", "Python"),
            "job_catalog": _encoded("first.md", "### 1. First | 甲公司"),
        },
        {
            "resume": _encoded("second.txt", "RAG"),
            "job_catalog": _encoded("second.md", "### 1. Second | 乙公司"),
        },
    )
    async with agent_client as client:
        first = await client.post("/agent/runs", json=requests[0])
        second = await client.post("/agent/runs", json=requests[1])
        response = await client.get("/agent/runs", params={"limit": 1})

    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()] == [second.json()["run_id"]]
    assert first.json()["run_id"] != second.json()["run_id"]


@pytest.mark.asyncio
async def test_agent_run_diff_compares_versions_without_raw_text(
    agent_client: AsyncClient,
) -> None:
    base_request = {
        "resume": _encoded("private.txt", "Python DIFF_PRIVATE_SENTINEL"),
        "job_catalog": _encoded(
            "jobs.md",
            "### 1. Agent | 甲公司\n**基本信息**\n- 每周 4 天\n**任职要求**\n- Python",
        ),
        "auto_decision_signals": True,
        "candidate_availability": {"weekly_days": 5},
    }
    target_request = {
        **base_request,
        "candidate_availability": {"weekly_days": 4},
    }
    async with agent_client as client:
        base = await client.post("/agent/runs", json=base_request)
        target = await client.post("/agent/runs", json=target_request)
        response = await client.get(
            f"/agent/runs/{base.json()['run_id']}/diff/{target.json()['run_id']}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_document_changed"] is False
    assert payload["job_catalog_document_changed"] is False
    assert payload["confirmation_changed"] is True
    assert "DIFF_PRIVATE_SENTINEL" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_agent_run_snapshot_returns_404_for_unknown_id(
    agent_client: AsyncClient,
) -> None:
    async with agent_client as client:
        response = await client.get("/agent/runs/00000000-0000-0000-0000-000000000000")
        document_response = await client.get(
            "/agent/documents/00000000-0000-0000-0000-000000000000"
        )
        confirmation_response = await client.get(
            "/agent/confirmations/00000000-0000-0000-0000-000000000000"
        )
        diff_response = await client.get(
            "/agent/runs/00000000-0000-0000-0000-000000000000/diff/"
            "00000000-0000-0000-0000-000000000001"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "agent run not found"
    assert document_response.status_code == 404
    assert document_response.json()["detail"] == "document not found"
    assert confirmation_response.status_code == 404
    assert confirmation_response.json()["detail"] == "confirmation version not found"
    assert diff_response.status_code == 404
    assert diff_response.json()["detail"] == "agent run not found"


@pytest.mark.asyncio
async def test_agent_api_accepts_candidate_availability_confirmation(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded(
            "jobs.md",
            "### 1. 实习岗位 | 甲公司\n**基本信息**\n- 每周 4 天；连续 3 个月",
        ),
        "auto_decision_signals": True,
        "candidate_availability": {"weekly_days": 5, "duration_months": 2},
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 200
    items = {
        item["name"]: item
        for item in response.json()["decision_signal_extractions"][0]["hard_constraints"]
    }
    assert items["weekly_days"]["candidate_confirmation"]["source"] == "user_confirmation"
    assert items["duration_months"]["status"] == "unmet"


@pytest.mark.asyncio
async def test_agent_api_rejects_availability_without_automatic_signals(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded("jobs.md", "### 1. 实习岗位 | 甲公司"),
        "candidate_availability": {"weekly_days": 5},
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agent_api_accepts_candidate_direction_preferences(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded(
            "jobs.md",
            "### 1. AI Infra 实习岗位 | 甲公司\n**岗位职责**\n- 建设智能运维平台",
        ),
        "auto_decision_signals": True,
        "candidate_direction_preferences": {"ai_infrastructure": 0.8},
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 200
    direction = response.json()["decision_signal_extractions"][0]["directions"][0]
    assert direction["candidate_confirmation"] == {
        "score": 0.8,
        "source": "user_confirmation",
    }


@pytest.mark.asyncio
async def test_agent_api_rejects_direction_preferences_without_automatic_signals(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded("jobs.md", "### 1. 实习岗位 | 甲公司"),
        "candidate_direction_preferences": {"ai_infrastructure": 0.8},
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agent_api_rejects_direction_preference_outside_unit_interval(
    agent_client: AsyncClient,
) -> None:
    request = {
        "resume": _encoded("resume.txt", "Python"),
        "job_catalog": _encoded("jobs.md", "### 1. 实习岗位 | 甲公司"),
        "auto_decision_signals": True,
        "candidate_direction_preferences": {"ai_infrastructure": 1.1},
    }

    async with agent_client as client:
        response = await client.post("/agent/runs", json=request)

    assert response.status_code == 422


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
