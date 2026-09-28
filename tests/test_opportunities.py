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
    assert payload["data_as_of"] == "2026-09-14"
    assert payload["freshness"] == "historical_snapshot"
    assert len(payload["opportunities"]) >= 5
    assert {item["company"] for item in payload["opportunities"]} >= {
        "MiniMax",
        "字节跳动",
        "小红书",
    }
    assert all(item["source_url"].startswith("https://") for item in payload["opportunities"])
    assert all(item["verification_status"] != "live" for item in payload["opportunities"])


def test_assistant_preview_routes_job_and_resume_intents() -> None:
    jobs = _request("POST", "/assistant/messages", {"message": "帮我找 AI Agent 实习"})
    resume = _request("POST", "/assistant/messages", {"message": "怎么上传简历匹配?"})
    other = _request("POST", "/assistant/messages", {"message": "你好"})

    assert jobs.status_code == 200
    assert jobs.json()["suggested_action"] == "view_opportunities"
    assert "核验快照" in jobs.json()["answer"]
    assert jobs.json()["mode"] == "typed_preview"
    assert resume.status_code == 200
    assert resume.json()["suggested_action"] == "upload_resume"
    assert other.status_code == 200
    assert other.json()["suggested_action"] == "none"
    assert "尚未联网自主搜索" in other.json()["answer"]


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
            "source_id": "verified-snapshot-2026-09-14",
            "status": "success",
            "fetched_at": "2026-09-14T00:00:00Z",
            "leads": payload["leads"],
            "error_code": None,
        }
    ]
    assert len(payload["leads"]) == 2
    assert {lead["company"] for lead in payload["leads"]} == {"MiniMax"}


def test_monitoring_sources_expose_companies_urls_and_keywords() -> None:
    response = _request("GET", "/monitoring/sources")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 32
    assert payload[0] == {
        "source_id": "tencent-careers",
        "company": "腾讯",
        "url": "https://careers.tencent.com/",
        "keywords": ["Agent Memory", "RAG", "知识图谱", "评测", "向量检索"],
        "pool": "anchor",
        "regions": ["中国"],
        "why_watch": "业务场景广，覆盖 Agent、内容、搜索与基础平台。",
    }
    assert payload[-1]["company"] == "Arize AI"


def test_homepage_recommendation_api_returns_six_anchor_and_three_focused() -> None:
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
    assert len(leads) == 9
    assert [lead["company_pool"] for lead in leads[:6]] == ["anchor"] * 6
    assert [lead["company_pool"] for lead in leads[6:]] == ["focused_ai"] * 3
