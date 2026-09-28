import base64
from collections.abc import Iterator
from typing import Any, cast

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_RUN_ID = "00000000-0000-0000-0000-000000000301"
_RUN_RESPONSE: dict[str, Any] = {
    "run_id": _RUN_ID,
    "state": "complete",
    "candidate": {
        "document_id": "00000000-0000-0000-0000-000000000401",
        "source_name": "resume.txt",
        "skills": [],
    },
    "job_catalog_document_id": "00000000-0000-0000-0000-000000000402",
    "total_jobs": 1,
    "considered_jobs": 1,
    "excluded_inactive_jobs": 0,
    "matches": [
        {
            "catalog_number": 1,
            "title": "Agent Intern",
            "company": "[COMPANY_A]",
            "source_url": None,
            "score": 82.5,
            "skill_score": 75,
            "hard_compatibility": 1,
            "direction_alignment": 0.9,
            "decision_explanations": [],
            "required_coverage": 0.75,
            "preferred_coverage": None,
            "contextual_coverage": None,
            "matched_required": [],
            "missing_required": [],
            "matched_preferred": [],
            "missing_preferred": [],
            "matched_contextual": [],
        }
    ],
    "decision_signal_extractions": [],
    "gap_analysis": {
        "analyzed_jobs": 1,
        "gaps": [
            {
                "skill": "CUDA",
                "required_by_jobs": 1,
                "preferred_by_jobs": 0,
                "affected_catalog_numbers": [1],
                "priority_score": 100,
                "priority": "high",
                "job_evidence": [],
            }
        ],
        "strengths": [],
    },
    "action_plan": None,
    "action_plan_review": None,
    "steps": [{"name": "rank_jobs", "role": "matcher", "status": "complete", "summary": "完成"}],
    "warnings": ["结果仍需人工确认。"],
}
_HISTORY_ITEM: dict[str, Any] = {
    "schema_version": 2,
    "run_id": _RUN_ID,
    "created_at": "2026-09-28T12:00:00Z",
    "state": "complete",
    "candidate_document_id": "00000000-0000-0000-0000-000000000401",
    "job_catalog_document_id": "00000000-0000-0000-0000-000000000402",
    "candidate_document_reference_id": None,
    "job_catalog_document_reference_id": None,
    "candidate_confirmation_version_id": None,
    "total_jobs": 1,
    "considered_jobs": 1,
    "excluded_inactive_jobs": 0,
    "request": {
        "top_k": 3,
        "include_inactive": False,
        "auto_decision_signals": True,
        "candidate_availability": {"weekly_days": 5, "duration_months": 12},
        "candidate_direction_preferences": {"agent_llm_application": 1},
        "use_llm": False,
    },
    "matches": [],
    "gaps": [],
    "action_plan": None,
    "action_plan_review": None,
    "steps": [{"name": "rank_jobs", "role": "matcher", "status": "complete"}],
    "warning_count": 1,
}
_DEFERRED_AGENT_FETCH_SCRIPT = """
(() => {
    const originalFetch = window.fetch.bind(window);
    let pending = null;
    window.__hasPendingAgentRun = () => pending !== null;
    window.__resolveAgentRun = (payload) => {
        pending(new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        }));
        pending = null;
    };
    window.fetch = (input, options = {}) => {
        const path = typeof input === "string" ? input : input.url;
        if (path !== "/agent/runs") return originalFetch(input, options);
        return new Promise((resolve) => { pending = resolve; });
    };
})();
"""


@pytest.fixture
def file_agent_page(
    page: Page, live_server_url: str
) -> Iterator[tuple[Page, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []

    def fulfill_run(route: Route) -> None:
        payload = route.request.post_data_json
        assert isinstance(payload, dict)
        requests.append(cast(dict[str, Any], payload))
        route.fulfill(json=_RUN_RESPONSE)

    page.route("**/agent/runs", fulfill_run)
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=[_HISTORY_ITEM]))
    page.goto(live_server_url)

    yield page, requests


def test_file_agent_submits_base64_confirmations_and_refreshes_history(
    file_agent_page: tuple[Page, list[dict[str, Any]]],
) -> None:
    page, requests = file_agent_page
    page.locator("#agent-resume").set_input_files(
        {"name": "resume.txt", "mimeType": "text/plain", "buffer": b"Python Agent"}
    )
    page.locator("#agent-jobs").set_input_files(
        {
            "name": "jobs.md",
            "mimeType": "text/markdown",
            "buffer": b"### 1. Agent Intern | Company\n**Requirements**\n- Python",
        }
    )
    page.locator("#agent-auto-signals").check()
    page.locator("#agent-weekly-days").fill("5")
    page.locator("#agent-duration-months").fill("12")
    page.locator("#direction-agent").fill("1")

    page.locator("#file-agent-form button[type='submit']").click()

    expect(page.locator("#agent-result")).to_be_visible()
    expect(page.locator("#agent-run-status")).to_have_text("complete")
    expect(page.locator("#agent-match-list")).to_contain_text("Agent Intern")
    expect(page.locator("#agent-match-list")).to_contain_text("82.5")
    expect(page.locator("#agent-gap-list")).to_contain_text("CUDA")
    expect(page.locator("#history-count")).to_have_text("1 次运行")

    assert len(requests) == 1
    payload = requests[0]
    assert payload["resume"]["filename"] == "resume.txt"
    assert base64.b64decode(payload["resume"]["content"]) == b"Python Agent"
    assert payload["job_catalog"]["filename"] == "jobs.md"
    assert payload["auto_decision_signals"] is True
    assert payload["candidate_availability"] == {"weekly_days": 5, "duration_months": 12}
    assert payload["candidate_direction_preferences"]["agent_llm_application"] == 1


def test_confirmation_controls_follow_auto_signal_toggle(page: Page, live_server_url: str) -> None:
    page.goto(live_server_url)

    expect(page.locator("#agent-weekly-days")).to_be_disabled()
    expect(page.locator("#direction-agent")).to_be_disabled()

    page.locator("#agent-auto-signals").check()

    expect(page.locator("#agent-weekly-days")).to_be_enabled()
    expect(page.locator("#direction-agent")).to_be_enabled()


def test_docx_llm_request_omits_disabled_confirmations(
    page: Page,
    live_server_url: str,
) -> None:
    requests: list[dict[str, Any]] = []

    def fulfill_run(route: Route) -> None:
        payload = route.request.post_data_json
        assert isinstance(payload, dict)
        requests.append(cast(dict[str, Any], payload))
        route.fulfill(json=_RUN_RESPONSE)

    page.route("**/agent/runs", fulfill_run)
    page.route("**/agent/runs?limit=20", lambda route: route.fulfill(json=[]))
    page.goto(live_server_url)
    page.locator("#agent-resume").set_input_files(
        {
            "name": "resume.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "buffer": b"PK\x03\x04docx",
        }
    )
    page.locator("#agent-jobs").set_input_files(
        {"name": "jobs.md", "mimeType": "text/markdown", "buffer": b"job"}
    )
    page.locator("#agent-use-llm").check()

    page.locator("#file-agent-form button[type='submit']").click()
    expect(page.locator("#agent-run-status")).to_have_text("complete")

    payload = requests[0]
    assert payload["use_llm"] is True
    assert base64.b64decode(payload["resume"]["content"]) == b"PK\x03\x04docx"
    assert "candidate_availability" not in payload
    assert "candidate_direction_preferences" not in payload


def test_agent_failure_restores_submit_button(page: Page, live_server_url: str) -> None:
    page.route(
        "**/agent/runs",
        lambda route: route.fulfill(status=422, json={"detail": "岗位目录无法解析"}),
    )
    page.goto(live_server_url)
    page.locator("#agent-resume").set_input_files(
        {"name": "resume.txt", "mimeType": "text/plain", "buffer": b"resume"}
    )
    page.locator("#agent-jobs").set_input_files(
        {"name": "jobs.md", "mimeType": "text/markdown", "buffer": b"invalid"}
    )

    button = page.locator("#file-agent-form button[type='submit']")
    button.click()

    expect(page.locator("#agent-run-status")).to_have_text("运行失败")
    expect(page.locator("#agent-warning")).to_have_text("岗位目录无法解析")
    expect(button).to_be_enabled()
    expect(button).to_have_text("运行文件 Agent")


def test_changed_file_invalidates_pending_agent_response(
    page: Page,
    live_server_url: str,
) -> None:
    page.add_init_script(script=_DEFERRED_AGENT_FETCH_SCRIPT)
    page.goto(live_server_url)
    page.locator("#agent-resume").set_input_files(
        {"name": "resume.txt", "mimeType": "text/plain", "buffer": b"old resume"}
    )
    page.locator("#agent-jobs").set_input_files(
        {"name": "jobs.md", "mimeType": "text/markdown", "buffer": b"job"}
    )
    button = page.locator("#file-agent-form button[type='submit']")
    button.click()
    page.wait_for_function("window.__hasPendingAgentRun()")

    page.locator("#agent-resume").set_input_files(
        {"name": "new.txt", "mimeType": "text/plain", "buffer": b"new resume"}
    )
    page.evaluate("payload => window.__resolveAgentRun(payload)", _RUN_RESPONSE)

    expect(page.locator("#agent-run-status")).to_have_text("有修改")
    expect(page.locator("#agent-result")).to_be_hidden()
    expect(button).to_be_enabled()
