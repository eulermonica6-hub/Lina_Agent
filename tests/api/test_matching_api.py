from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from lina_agent.config import Settings
from lina_agent.main import create_app

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    import json

    return cast(
        dict[str, Any],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )


@pytest.fixture
def test_app_client() -> AsyncClient:
    app = create_app(Settings(app_name="Lina Test", environment="test"))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_create_profile_job_and_run_match(test_app_client: AsyncClient) -> None:
    async with test_app_client as client:
        profile_response = await client.post(
            "/profiles",
            json=load_fixture("candidate_profile.json"),
        )
        assert profile_response.status_code == 201
        job_response = await client.post(
            "/jobs",
            json=load_fixture("target_job.json"),
        )
        assert job_response.status_code == 201
        match_response = await client.post(
            "/matches",
            json={
                "candidate_id": profile_response.json()["id"],
                "job_id": job_response.json()["id"],
            },
        )

    assert profile_response.json()["graduation_year"] == 2028
    assert job_response.json()["constraints"]["graduation_years"] == [2027]
    assert match_response.status_code == 200
    assert match_response.json() == {
        "is_eligible": False,
        "reasons": ["graduation_year"],
    }


@pytest.mark.asyncio
async def test_match_returns_404_for_unknown_candidate(test_app_client: AsyncClient) -> None:
    async with test_app_client as client:
        job_response = await client.post("/jobs", json=load_fixture("target_job.json"))
        assert job_response.status_code == 201
        response = await client.post(
            "/matches",
            json={
                "candidate_id": str(UUID(int=0)),
                "job_id": job_response.json()["id"],
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("candidate profile")


@pytest.mark.asyncio
async def test_parse_job_description_returns_constraints_and_evidence(
    test_app_client: AsyncClient,
) -> None:
    description = "工作地点：上海。要求 2027 届本科及以上学历，具备 2 年以上工作经验。"

    async with test_app_client as client:
        response = await client.post("/jobs/parse", json={"description": description})

    assert response.status_code == 200
    payload = response.json()
    assert payload["constraints"] == {
        "minimum_education": "bachelor",
        "graduation_years": [2027],
        "minimum_years_of_experience": 2.0,
        "locations": ["上海"],
    }
    education_evidence = payload["evidence"]["minimum_education"]
    assert education_evidence["text"] == "本科及以上学历"
    assert (
        description[education_evidence["start_offset"] : education_evidence["end_offset"]]
        == education_evidence["text"]
    )
