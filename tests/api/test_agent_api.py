import base64

import pytest
from httpx import ASGITransport, AsyncClient

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
