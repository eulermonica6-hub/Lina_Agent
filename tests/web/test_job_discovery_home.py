import base64
from typing import Any, cast

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_FEED: dict[str, Any] = {
    "data_as_of": "2026-09-28",
    "freshness": "verified_recommendations",
    "source_note": "已复核详情和投递入口。",
    "opportunities": [
        {
            "opportunity_id": "minimax-agent",
            "company": "MiniMax",
            "title": "Agent 研发实习生-AI Infra",
            "location": "上海",
            "direction": "AI Infra",
            "source_url": "https://example.com/minimax",
            "last_verified_at": "2026-09-28",
            "verification_status": "live",
            "highlights": ["Python", "Agent", "RAG/MCP"],
        },
        {
            "opportunity_id": "bytedance-risk",
            "company": "字节跳动",
            "title": "国际支付风控算法实习生",
            "location": "上海",
            "direction": "机器学习",
            "source_url": "https://example.com/bytedance",
            "last_verified_at": "2026-09-28",
            "verification_status": "live",
            "highlights": ["ML", "LLM", "图模型"],
        },
    ],
}
_RECOMMENDATION_RESPONSE: dict[str, Any] = {
    "sources": [],
    "leads": [
        {
            "lead_id": f"snapshot:{item['opportunity_id']}",
            "source_id": "verified-snapshot-2026-09-28",
            "external_id": item["opportunity_id"],
            "company": item["company"],
            "title": item["title"],
            "locations": [item["location"]],
            "direction": item["direction"],
            "source_url": item["source_url"],
            "captured_at": "2026-09-28T00:00:00Z",
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
    expect(page.locator("#opportunity-title")).to_have_text("今天为你推荐的 6 个岗位")
    expect(page.locator("#opportunity-list")).to_contain_text("MiniMax")
    expect(page.locator(".opportunity-logo img")).to_have_count(2)
    expect(page.locator(".opportunity-logo img").first).to_have_attribute("alt", "MiniMax logo")
    expect(page.locator("#opportunity-freshness")).to_contain_text("2026-09-28")
    expect(page.locator("#opportunity-freshness")).to_contain_text("已复核推荐")
    expect(page.locator("#opportunity-freshness")).to_contain_text("每日轮换")
    expect(page.locator("#opportunity-location")).to_have_value("上海")
    expect(page.locator("#opportunity-job-type")).to_have_value("early_career")
    expect(page.locator("#opportunity-filters")).not_to_have_attribute("open", "")
    expect(page.locator("#profile-form")).to_be_hidden()
    expect(page.locator("#run-history")).to_be_hidden()
    expect(page.locator("a[href='/workbench']")).to_be_visible()
    expect(page.locator("a[href='/inbox']")).to_be_visible()
    expect(page.locator("#inbox-count")).to_have_text("0")
    expect(page.locator("#opportunity-list article").first).to_be_in_viewport()
    expect(page.locator("#chat-toggle")).to_contain_text("和 Lina 对话")
    expect(page.locator(".topbar #chat-toggle")).to_be_visible()
    expect(page.locator("#run-state")).to_be_hidden()
    expect(page.locator("#chat-panel")).to_be_visible()
    expect(page.locator("#chat-toggle")).to_have_attribute("aria-expanded", "true")
    expect(page.locator("body")).to_have_class("home-page chat-open")
    expect(page.get_by_text("COMPANY RADAR")).to_have_count(0)
    expect(page.locator(".opportunity-pool")).to_have_count(0)

    resize_handle = page.locator("#chat-resize-handle")
    expect(resize_handle).to_be_visible()
    resize_handle.press("ArrowLeft")
    expect(resize_handle).to_have_attribute("aria-valuenow", "416")
    resize_box = resize_handle.bounding_box()
    assert resize_box is not None
    page.mouse.move(resize_box["x"] + resize_box["width"] / 2, 120)
    page.mouse.down()
    page.mouse.move(resize_box["x"] - 32, 120, steps=4)
    page.mouse.up()
    resized_width = page.locator("#chat-panel").evaluate(
        "panel => Math.round(panel.getBoundingClientRect().width)"
    )
    assert resized_width > 416
    assert resize_handle.get_attribute("aria-valuenow") == str(resized_width)

    page.locator("#chat-close").click()
    expect(page.locator("#chat-panel")).to_be_hidden()
    expect(page.locator("body")).not_to_have_class("chat-open")
    page.locator("#chat-toggle").click()
    expect(page.locator("#chat-message")).to_be_focused()


def test_mobile_home_keeps_jobs_and_chat_visible_without_overlap(
    page: Page,
    live_server_url: str,
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )
    page.goto(live_server_url)

    first_card = page.locator("#opportunity-list article").first
    chat = page.locator("#chat-toggle")
    expect(page.locator("#chat-panel")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") is True
    page.locator("#chat-close").click()
    expect(first_card).to_be_in_viewport()
    expect(chat).to_be_in_viewport()
    expect(chat).to_contain_text("和 Lina 对话")
    expect(page.locator("#opportunity-filters")).not_to_have_attribute("open", "")
    boxes = page.evaluate(
        """() => {
            const card = document
                .querySelector('#opportunity-list article')
                .getBoundingClientRect();
            const chat = document.querySelector('#chat-toggle').getBoundingClientRect();
            return { card, chat, overflow: document.documentElement.scrollWidth > innerWidth };
        }"""
    )
    assert boxes["overflow"] is False
    assert (
        boxes["chat"]["bottom"] <= boxes["card"]["top"]
        or boxes["chat"]["top"] >= boxes["card"]["bottom"]
        or boxes["chat"]["left"] >= boxes["card"]["right"]
    )


def test_chat_sends_message_and_routes_suggested_action(page: Page, live_server_url: str) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )

    def reply(route: Route) -> None:
        route.fulfill(
            json={
                "answer": "我已加载 2 条官方核验快照。",
                "mode": "tool_execution",
                "suggested_action": "view_opportunities",
                "tool": "job_search",
                "missing_fields": [],
                "opportunities": [
                    {
                        "external_id": "minimax-agent",
                        "company": "MiniMax",
                        "title": "Agent 研发实习生-AI Infra",
                        "locations": ["上海"],
                        "direction": "AI Infra",
                        "source_url": "https://example.com/minimax",
                        "source_id": "verified-snapshot-2026-09-28",
                        "source_status": "success",
                        "highlights": ["Python", "Agent"],
                    }
                ],
                "inbox_items": [],
            }
        )

    page.route("**/assistant/messages", reply)
    page.goto(live_server_url)
    expect(page.locator("[data-chat-prompt]")).to_have_count(3)
    page.get_by_role("button", name="帮我找上海的 Agent 实习").click()

    expect(page.locator("#chat-log")).to_contain_text("帮我找上海的 Agent 实习")
    expect(page.locator("#chat-log")).to_contain_text("我已加载 2 条官方核验快照")
    expect(page.locator(".chat-tool-results")).to_contain_text(
        "MiniMax · Agent 研发实习生-AI Infra"
    )
    expect(page.locator(".chat-tool-results")).to_contain_text(
        "verified-snapshot-2026-09-28 · success"
    )
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
                    "source_id": "verified-snapshot-2026-09-28",
                    "status": "success",
                    "fetched_at": "2026-09-14T00:00:00Z",
                    "leads": [],
                    "error_code": None,
                }
            ],
            "leads": [
                {
                    "lead_id": "snapshot:minimax-infra",
                    "source_id": "verified-snapshot-2026-09-28",
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
    page.locator("#opportunity-filters summary").click()
    page.locator("#opportunity-query").fill("infra")
    page.locator("#opportunity-company").select_option("MiniMax")
    page.locator("#opportunity-location").fill("上海")
    page.locator("#opportunity-search-form button[type='submit']").click()

    expect(page.locator("#opportunity-list article")).to_have_count(1)
    expect(page.locator("#opportunity-list")).to_contain_text("Agent 研发实习生-AI Infra")
    expect(page.locator("#opportunity-freshness")).to_contain_text("1 个来源正常")


def test_home_does_not_expose_internal_company_pools(
    page: Page,
    live_server_url: str,
) -> None:
    page.route(
        "**/opportunities/recommended",
        lambda route: route.fulfill(json=_RECOMMENDATION_RESPONSE),
    )
    page.goto(live_server_url)

    expect(page.get_by_text("COMPANY RADAR")).to_have_count(0)
    expect(page.get_by_text("主池 · 平台与大厂")).to_have_count(0)
    expect(page.get_by_text("探索池 · 小而美 / 专注型 AI")).to_have_count(0)


def test_homepage_recommendations_use_habits_and_six_card_layout(
    page: Page,
    live_server_url: str,
) -> None:
    requests: list[dict[str, Any]] = []
    leads: list[dict[str, Any]] = []
    for index in range(6):
        leads.append(
            {
                "lead_id": f"lead-{index}",
                "source_id": "test",
                "external_id": f"external-{index}",
                "company": f"Company {index}",
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
    expect(cards).to_have_count(6)
    expect(cards.locator(".opportunity-pool")).to_have_count(0)
    assert requests == [
        {
            "preferred_companies": ["Apple"],
            "preferred_directions": ["Agent"],
            "recent_companies": ["MiniMax"],
            "preferred_locations": ["上海", "远程"],
            "preferred_job_types": ["internship", "campus"],
            "limit": 6,
        }
    ]
