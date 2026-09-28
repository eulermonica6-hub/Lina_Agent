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


def test_home_loads_opportunity_snapshots_and_opens_chat(page: Page, live_server_url: str) -> None:
    page.route("**/opportunities", lambda route: route.fulfill(json=_FEED))
    page.goto(live_server_url)

    expect(page.locator("#opportunity-list article")).to_have_count(2)
    expect(page.locator("#opportunity-list")).to_contain_text("MiniMax")
    expect(page.locator("#opportunity-freshness")).to_contain_text("2026-09-14")
    expect(page.locator("#opportunity-freshness")).to_contain_text("历史核验快照")

    page.locator("#chat-toggle").click()
    expect(page.locator("#chat-panel")).to_be_visible()
    expect(page.locator("#chat-message")).to_be_focused()
    page.locator("#chat-close").click()
    expect(page.locator("#chat-panel")).to_be_hidden()


def test_chat_sends_message_and_routes_suggested_action(page: Page, live_server_url: str) -> None:
    page.route("**/opportunities", lambda route: route.fulfill(json=_FEED))

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
    page.route("**/opportunities", lambda route: route.fulfill(json=_FEED))

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
