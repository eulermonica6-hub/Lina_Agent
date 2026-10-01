import asyncio

from httpx import ASGITransport, AsyncClient, Response

from lina_agent.config import Settings
from lina_agent.main import create_app


def _request(method: str, path: str, json: object | None = None) -> Response:
    app = create_app(Settings(app_name="Lina Test", environment="test"))

    async def send() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_opportunity_feed_exposes_dated_official_snapshots() -> None:
    response = _request("GET", "/opportunities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_as_of"] == "2026-09-28"
    assert payload["freshness"] == "verified_recommendations"
    assert len(payload["opportunities"]) == 6
    companies = [item["company"] for item in payload["opportunities"]]
    assert sum(company in {"字节跳动", "小红书"} for company in companies) == 2
    assert sum(company in {"Apple", "NVIDIA"} for company in companies) == 2
    assert sum(company in {"MiniMax", "Unstructured"} for company in companies) == 2
    assert all(item["source_url"].startswith("https://") for item in payload["opportunities"])
    assert all(item["verification_status"] == "live" for item in payload["opportunities"])
    assert all("company_pool" not in item for item in payload["opportunities"])


def test_live_job_source_is_wired_outside_test_environment() -> None:
    test_app = create_app(Settings(app_name="Lina Test", environment="test", database_path=None))
    development_app = create_app(
        Settings(app_name="Lina Dev", environment="development", database_path=None)
    )

    assert test_app.state.job_search_service.source_ids == ("verified-snapshot-2026-09-28",)
    assert development_app.state.job_search_service.source_ids == (
        "verified-snapshot-2026-09-28",
        "nvidia-careers",
    )
    assert development_app.state.job_recommendation_service.source_ids == (
        "verified-snapshot-2026-09-28",
    )


def test_assistant_calls_tools_and_routes_guidance() -> None:
    jobs = _request(
        "POST",
        "/assistant/messages",
        {"message": "帮我找上海 Agent 实习"},
    )
    clarification = _request("POST", "/assistant/messages", {"message": "帮我找岗位"})
    comparison = _request("POST", "/assistant/messages", {"message": "比较岗位"})
    resume = _request("POST", "/assistant/messages", {"message": "怎么上传简历匹配?"})
    other = _request("POST", "/assistant/messages", {"message": "你好"})

    assert jobs.status_code == 200
    assert jobs.json()["mode"] == "tool_execution"
    assert jobs.json()["tool"] == "job_search"
    assert jobs.json()["suggested_action"] == "view_opportunities"
    assert jobs.json()["opportunities"]
    assert all(item["source_url"].startswith("https://") for item in jobs.json()["opportunities"])
    assert all(item["source_status"] == "success" for item in jobs.json()["opportunities"])
    assert clarification.json()["mode"] == "clarification"
    assert clarification.json()["missing_fields"] == ["location", "job_type", "direction"]
    assert comparison.json()["mode"] == "tool_execution"
    assert comparison.json()["tool"] == "job_compare"
    assert "unknown" in comparison.json()["answer"]
    assert resume.status_code == 200
    assert resume.json()["suggested_action"] == "upload_resume"
    assert other.status_code == 200
    assert other.json()["suggested_action"] == "none"
    assert "搜索岗位" in other.json()["answer"]


def test_manual_opportunity_search_returns_leads_and_source_health() -> None:
    response = _request(
        "POST",
        "/opportunities/search",
        {
            "query": "agent",
            "companies": ["MiniMax"],
            "locations": ["上海"],
            "max_results": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"] == [
        {
            "source_id": "verified-snapshot-2026-09-28",
            "status": "success",
            "fetched_at": "2026-09-28T00:00:00Z",
            "leads": payload["leads"],
            "error_code": None,
        }
    ]
    assert len(payload["leads"]) == 2
    assert {lead["company"] for lead in payload["leads"]} == {"MiniMax"}
    assert all("company_pool" not in lead for lead in payload["leads"])
    assert all("deduplication_key" not in lead for lead in payload["leads"])


def test_homepage_recommendation_api_returns_two_per_company_segment() -> None:
    response = _request(
        "POST",
        "/opportunities/recommended",
        {
            "preferred_companies": ["Apple"],
            "preferred_directions": ["Agent"],
            "recent_companies": ["MiniMax"],
            "week_start": "2026-09-28",
        },
    )

    assert response.status_code == 200
    leads = response.json()["leads"]
    assert len(leads) == 6
    companies = [lead["company"] for lead in leads]
    assert sum(company in {"字节跳动", "小红书"} for company in companies) == 2
    assert sum(company in {"Apple", "NVIDIA"} for company in companies) == 2
    assert sum(company in {"MiniMax", "Unstructured"} for company in companies) == 2
    assert all(lead["verification_status"] == "live" for lead in leads)
    assert all("company_pool" not in lead for lead in leads)
