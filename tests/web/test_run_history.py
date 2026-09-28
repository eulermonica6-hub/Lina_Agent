from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_BASE_ID = "00000000-0000-0000-0000-000000000101"
_TARGET_ID = "00000000-0000-0000-0000-000000000102"
_HISTORY: list[dict[str, Any]] = [
    {
        "schema_version": 2,
        "run_id": _TARGET_ID,
        "created_at": "2026-09-28T10:30:00Z",
        "state": "complete",
        "candidate_document_id": "00000000-0000-0000-0000-000000000201",
        "job_catalog_document_id": "00000000-0000-0000-0000-000000000202",
        "candidate_document_reference_id": "00000000-0000-0000-0000-000000000211",
        "job_catalog_document_reference_id": "00000000-0000-0000-0000-000000000212",
        "candidate_confirmation_version_id": "00000000-0000-0000-0000-000000000213",
        "total_jobs": 2,
        "considered_jobs": 2,
        "excluded_inactive_jobs": 0,
        "request": {
            "top_k": 2,
            "include_inactive": False,
            "auto_decision_signals": True,
            "candidate_availability": None,
            "candidate_direction_preferences": None,
            "use_llm": False,
        },
        "matches": [
            {
                "catalog_number": 2,
                "title": "AI Infra Intern",
                "company": "[COMPANY_B]",
                "score": 75,
                "skill_score": 70,
                "hard_compatibility": 1,
                "direction_alignment": 0.8,
                "matched_required_skills": ["Python"],
                "missing_required_skills": ["CUDA"],
                "matched_preferred_skills": [],
                "missing_preferred_skills": [],
            },
            {
                "catalog_number": 1,
                "title": "Agent Intern",
                "company": "[COMPANY_A]",
                "score": 65,
                "skill_score": 65,
                "hard_compatibility": 1,
                "direction_alignment": 1,
                "matched_required_skills": ["Python"],
                "missing_required_skills": [],
                "matched_preferred_skills": [],
                "missing_preferred_skills": [],
            },
        ],
        "gaps": [],
        "action_plan": None,
        "action_plan_review": None,
        "steps": [{"name": "rank_jobs", "role": "matcher", "status": "complete"}],
        "warning_count": 0,
    },
    {
        "schema_version": 2,
        "run_id": _BASE_ID,
        "created_at": "2026-09-28T09:30:00Z",
        "state": "complete",
        "candidate_document_id": "00000000-0000-0000-0000-000000000201",
        "job_catalog_document_id": "00000000-0000-0000-0000-000000000202",
        "candidate_document_reference_id": "00000000-0000-0000-0000-000000000211",
        "job_catalog_document_reference_id": "00000000-0000-0000-0000-000000000212",
        "candidate_confirmation_version_id": "00000000-0000-0000-0000-000000000214",
        "total_jobs": 2,
        "considered_jobs": 2,
        "excluded_inactive_jobs": 0,
        "request": {
            "top_k": 2,
            "include_inactive": False,
            "auto_decision_signals": True,
            "candidate_availability": None,
            "candidate_direction_preferences": None,
            "use_llm": False,
        },
        "matches": [],
        "gaps": [],
        "action_plan": None,
        "action_plan_review": None,
        "steps": [{"name": "rank_jobs", "role": "matcher", "status": "complete"}],
        "warning_count": 0,
    },
]
_DIFF = {
    "base_run_id": _BASE_ID,
    "target_run_id": _TARGET_ID,
    "candidate_document_changed": False,
    "job_catalog_document_changed": False,
    "confirmation_changed": True,
    "state_changed": False,
    "plan_changed": False,
    "base_ranking": [1, 2],
    "target_ranking": [2, 1],
    "added_catalog_numbers": [],
    "removed_catalog_numbers": [],
    "replaced_catalog_numbers": [],
    "ranking_changes": [
        {"catalog_number": 2, "base_position": 2, "target_position": 1, "position_delta": -1},
        {"catalog_number": 1, "base_position": 1, "target_position": 2, "position_delta": 1},
    ],
    "score_changes": [
        {
            "catalog_number": 2,
            "base_score": 60,
            "target_score": 75,
            "score_delta": 15,
            "skill_score_delta": 10,
            "hard_compatibility_changed": False,
            "direction_alignment_changed": True,
        }
    ],
    "added_gaps": ["CUDA"],
    "resolved_gaps": ["PyTorch"],
}


@pytest.fixture
def history_page(page: Page, live_server_url: str) -> Iterator[Page]:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=_HISTORY))
    page.route(
        f"**/agent/runs/{_BASE_ID}/diff/{_TARGET_ID}",
        lambda route: route.fulfill(json=_DIFF),
    )
    page.goto(live_server_url)

    yield page

    assert page_errors == []


def test_history_panel_loads_runs_and_renders_structured_diff(history_page: Page) -> None:
    page = history_page

    page.locator("#refresh-history").click()

    expect(page.locator("#history-count")).to_have_text("2 次运行")
    expect(page.locator("#base-run")).to_have_value(_BASE_ID)
    expect(page.locator("#target-run")).to_have_value(_TARGET_ID)
    expect(page.locator("#compare-runs")).to_be_enabled()

    page.locator("#compare-runs").click()

    expect(page.locator("#diff-panel")).to_be_visible()
    expect(page.locator("#diff-facts")).to_contain_text("确认事实已更新")
    expect(page.locator("#ranking-changes")).to_contain_text("岗位 2")
    expect(page.locator("#ranking-changes")).to_contain_text("上升 1 位")
    expect(page.locator("#score-changes")).to_contain_text("+15.0")
    expect(page.locator("#gap-changes")).to_contain_text("新增 CUDA")
    expect(page.locator("#gap-changes")).to_contain_text("解决 PyTorch")
    expect(page.locator("body")).not_to_contain_text("PRIVATE")


def test_history_panel_handles_empty_history(page: Page, live_server_url: str) -> None:
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=[]))
    page.goto(live_server_url)

    page.locator("#refresh-history").click()

    expect(page.locator("#history-count")).to_have_text("暂无运行")
    expect(page.locator("#history-empty")).to_be_visible()
    expect(page.locator("#compare-runs")).to_be_disabled()


def test_history_panel_recovers_from_load_error(page: Page, live_server_url: str) -> None:
    page.route(
        "**/agent/runs?limit=20",
        lambda route: route.fulfill(status=500, json={"detail": "历史服务暂不可用"}),
    )
    page.goto(live_server_url)

    page.locator("#refresh-history").click()

    expect(page.locator("#history-count")).to_have_text("加载失败")
    expect(page.locator("#history-empty")).to_have_text("历史服务暂不可用")
    expect(page.locator("#refresh-history")).to_be_enabled()
    expect(page.locator("#run-state span:last-child")).to_have_text("历史服务暂不可用")


def test_diff_button_recovers_from_request_error(page: Page, live_server_url: str) -> None:
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=_HISTORY))
    page.route(
        f"**/agent/runs/{_BASE_ID}/diff/{_TARGET_ID}",
        lambda route: route.fulfill(status=500, json={"detail": "比较暂不可用"}),
    )
    page.goto(live_server_url)
    page.locator("#refresh-history").click()

    page.locator("#compare-runs").click()

    expect(page.locator("#diff-panel")).to_be_hidden()
    expect(page.locator("#compare-runs")).to_be_enabled()
    expect(page.locator("#compare-runs")).to_have_text("比较变化")
    expect(page.locator("#run-state span:last-child")).to_have_text("比较暂不可用")
