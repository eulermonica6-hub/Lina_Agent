import pytest
from httpx import ASGITransport, AsyncClient

from lina_agent.config import Settings
from lina_agent.main import create_app


@pytest.mark.asyncio
async def test_sandbox_api_runs_repair_loop() -> None:
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/sandbox/runs",
            json={
                "source": "raise RuntimeError('broken')",
                "repair_candidates": ["print('fixed')"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["attempts"]) == 2
    assert payload["final_source"] == "print('fixed')"


@pytest.mark.asyncio
async def test_sandbox_api_reports_validation_failures() -> None:
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/sandbox/runs", json={"source": "import subprocess"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "allowlist" in payload["attempts"][0]["stderr"]
