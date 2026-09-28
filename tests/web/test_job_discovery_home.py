import base64
from typing import Any, cast

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_FEED: dict[str, Any] = {
    "data_as_of": "2026-09-14",
    "freshness": "historical_snapshot",
    "source_note": "官方页面人工核验快照，不代表当前仍在招聘。",
    "opportunities": [
        {
            "opportunity_id": "minimax-agent",
            "company": "MiniMax",
            "company_pool": "focused_ai",
            "title": "Agent 研发实习生-AI Infra",
            "location": "上海",
            "direction": "AI Infra",
            "source_url": "https://example.com/minimax",
            "last_verified_at": "2026-09-14",
            "verification_status": "needs_reverification",
            "highlights": ["Python", "Agent", "RAG/MCP"],
        },
        {
            "opportunity_id": "bytedance-risk",
            "company": "字节跳动",
            "company_pool": "anchor",
            "title": "国际支付风控算法实习生",
            "location": "上海",
            "direction": "机器学习",
            "source_url": "https://example.com/bytedance",
            "last_verified_at": "2026-09-14",
            "verification_status": "needs_reverification",
            "highlights": ["ML", "LLM", "图模型"],
        },
    ],
}
_RECOMMENDATION_RESPONSE: dict[str, Any] = {
    "sources": [],
    "leads": [
        {
            "lead_id": f"snapshot:{item['opportunity_id']}",
            "deduplication_key": item["opportunity_id"],
            "source_id": "verified-snapshot-2026-09-14",
            "external_id": item["opportunity_id"],
            "company": item["company"],
            "company_pool": item["company_pool"],
            "title": item["title"],
            "locations": [item["location"]],
            "direction": item["direction"],
            "source_url": item["source_url"],
            "captured_at": "2026-09-14T00:00:00Z",
            "verification_status": item["verification_status"],
            "highlights": item["highlights"],
        }
        for item in _FEED["opportunities"]
    ],
}


def test_home_loads_opportunity_snapshots_and_opens_chat(page: Page, live_server_url: str) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )
    page.goto(live_server_url)

    expect(page.locator("#opportunity-list article")).to_have_count(2)
    expect(page.locator("#opportunity-list")).to_contain_text("MiniMax")
    expect(page.locator("#opportunity-freshness")).to_contain_text("2026-09-14")
    expect(page.locator("#opportunity-freshness")).to_contain_text("历史核验快照")
    expect(page.locator("#opportunity-location")).to_have_value("上海")
    expect(page.locator("#opportunity-job-type")).to_have_value("early_career")
    expect(page.locator("#profile-form")).to_be_hidden()
    expect(page.locator("#run-history")).to_be_hidden()
    expect(page.locator("a[href='/workbench']")).to_be_visible()
    expect(page.locator("#monitoring-sources")).to_contain_text("32 个来源")
    expect(page.locator("#monitoring-sources")).to_contain_text("10 家主池")
    expect(page.locator("#monitoring-sources")).to_contain_text("22 家探索池")

    page.locator("#chat-toggle").click()
    expect(page.locator("#chat-panel")).to_be_visible()
    expect(page.locator("#chat-message")).to_be_focused()
    page.locator("#chat-close").click()
    expect(page.locator("#chat-panel")).to_be_hidden()


def test_chat_sends_message_and_routes_suggested_action(page: Page, live_server_url: str) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )

    def reply(route: Route) -> None:
        route.fulfill(
            json={
                "answer": "我已加载 2 条官方核验快照。",
                "mode": "typed_preview",
                "suggested_action": "view_opportunities",
            }
        )

    page.route("**/assistant/messages", reply)
    page.goto(live_server_url)
    page.locator("#chat-toggle").click()
    page.locator("#chat-message").fill("帮我找 Agent 实习")
    page.locator("#chat-form button[type='submit']").click()

    expect(page.locator("#chat-log")).to_contain_text("帮我找 Agent 实习")
    expect(page.locator("#chat-log")).to_contain_text("我已加载 2 条官方核验快照")
    expect(page.locator("#opportunities")).to_be_in_viewport()


def test_resume_only_matches_loaded_opportunity_feed(page: Page, live_server_url: str) -> None:
    requests: list[dict[str, Any]] = []
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )

    def run_agent(route: Route) -> None:
        payload = route.request.post_data_json
        assert isinstance(payload, dict)
        requests.append(cast(dict[str, Any], payload))
        route.fulfill(
            json={
                "state": "complete",
                "matches": [],
                "gap_analysis": {"gaps": []},
                "warnings": [],
            }
        )

    page.route("**/agent/runs", run_agent)
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=[]))
    page.goto(live_server_url)
    page.locator("#agent-resume").set_input_files(
        {"name": "resume.txt", "mimeType": "text/plain", "buffer": b"Python Agent"}
    )

    page.locator("#file-agent-form button[type='submit']").click()
    expect(page.locator("#agent-run-status")).to_have_text("complete")

    assert len(requests) == 1
    job_catalog = requests[0]["job_catalog"]
    assert job_catalog["filename"] == "lina-opportunity-snapshots.md"
    decoded = base64.b64decode(job_catalog["content"]).decode()
    assert "Agent 研发实习生-AI Infra | MiniMax" in decoded
    assert "国际支付风控算法实习生 | 字节跳动" in decoded


def test_manual_search_filters_feed_and_reports_source_health(
    page: Page,
    live_server_url: str,
) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )

    def search(route: Route) -> None:
        assert route.request.post_data_json == {
            "query": "infra",
            "companies": ["MiniMax"],
            "locations": ["上海"],
            "job_types": ["internship", "campus"],
            "max_results": 50,
        }
        response: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "verified-snapshot-2026-09-14",
                    "status": "success",
                    "fetched_at": "2026-09-14T00:00:00Z",
                    "leads": [],
                    "error_code": None,
                }
            ],
            "leads": [
                {
                    "lead_id": "snapshot:minimax-infra",
                    "deduplication_key": "minimax:infra:上海",
                    "source_id": "verified-snapshot-2026-09-14",
                    "external_id": "minimax-infra",
                    "company": "MiniMax",
                    "title": "Agent 研发实习生-AI Infra",
                    "locations": ["上海"],
                    "direction": "AI Infra",
                    "source_url": "https://example.com/minimax",
                    "captured_at": "2026-09-14T00:00:00Z",
                    "verification_status": "needs_reverification",
                    "highlights": ["Python", "Agent"],
                }
            ],
        }
        route.fulfill(json=response)

    page.route("**/opportunities/search", search)
    page.goto(live_server_url)
    page.locator("#opportunity-query").fill("infra")
    page.locator("#opportunity-company").select_option("MiniMax")
    page.locator("#opportunity-location").fill("上海")
    page.locator("#opportunity-search-form button[type='submit']").click()

    expect(page.locator("#opportunity-list article")).to_have_count(1)
    expect(page.locator("#opportunity-list")).to_contain_text("Agent 研发实习生-AI Infra")
    expect(page.locator("#opportunity-freshness")).to_contain_text("1 个来源正常")


def test_company_radar_displays_anchor_and_focused_ai_pools(
    page: Page,
    live_server_url: str,
) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )
    page.route(
        "**/companies",
        lambda route: route.fulfill(
            json=[
                {
                    "source_id": "tencent-careers",
                    "company": "腾讯",
                    "url": "https://careers.tencent.com/",
                    "keywords": ["RAG"],
                    "pool": "anchor",
                    "regions": ["中国"],
                    "why_watch": "平台型 AI 岗位覆盖广。",
                },
                {
                    "source_id": "llamaindex-careers",
                    "company": "LlamaIndex",
                    "url": "https://www.llamaindex.ai/careers",
                    "keywords": ["Agent", "RAG"],
                    "pool": "focused_ai",
                    "regions": ["美国", "远程"],
                    "why_watch": "Agent 与知识工作自动化方向高度集中。",
                },
            ]
        ),
    )
    page.goto(live_server_url)

    expect(page.locator("#anchor-company-list")).to_contain_text("腾讯")
    expect(page.locator("#focused-company-list")).to_contain_text("LlamaIndex")
    expect(page.locator("#focused-company-list")).to_contain_text("Agent 与知识工作自动化")


def test_homepage_recommendations_use_habits_and_six_three_layout(
    page: Page,
    live_server_url: str,
) -> None:
    requests: list[dict[str, Any]] = []
    leads: list[dict[str, Any]] = []
    for index in range(9):
        pool = "anchor" if index < 6 else "focused_ai"
        leads.append(
            {
                "lead_id": f"lead-{index}",
                "deduplication_key": f"key-{index}",
                "source_id": "test",
                "external_id": f"external-{index}",
                "company": f"Company {index}",
                "company_pool": pool,
                "title": f"Agent Role {index}",
                "locations": ["上海"],
                "direction": "Agent",
                "source_url": f"https://example.com/{index}",
                "captured_at": "2026-09-14T00:00:00Z",
                "verification_status": "needs_reverification",
                "highlights": ["Agent"],
            }
        )

    def recommend(route: Route) -> None:
        payload = route.request.post_data_json
        assert isinstance(payload, dict)
        requests.append(cast(dict[str, Any], payload))
        route.fulfill(json={"sources": [], "leads": leads})

    page.add_init_script(
        script="""
            localStorage.setItem("linaPreferredCompanies", JSON.stringify(["Apple"]));
            localStorage.setItem("linaPreferredDirections", JSON.stringify(["Agent"]));
            localStorage.setItem("linaRecentCompanies", JSON.stringify(["MiniMax"]));
        """
    )
    page.route("**/opportunities/recommended", recommend)
    page.goto(live_server_url)

    cards = page.locator("#opportunity-list article")
    expect(cards).to_have_count(9)
    expect(cards.locator(".opportunity-pool.anchor")).to_have_count(6)
    expect(cards.locator(".opportunity-pool.focused")).to_have_count(3)
    assert requests == [
        {
            "preferred_companies": ["Apple"],
            "preferred_directions": ["Agent"],
            "recent_companies": ["MiniMax"],
            "preferred_locations": ["上海", "远程"],
            "preferred_job_types": ["internship", "campus"],
            "limit": 9,
        }
    ]
