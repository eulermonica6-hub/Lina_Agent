from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_DEFERRED_FETCH_SCRIPT = """
(() => {
    const pending = new Map();

    window.__pendingFetchCount = (path) => (pending.get(path) || []).length;
    window.__resolveFetch = ({ path, status, payload }) => {
        const queue = pending.get(path) || [];
        const request = queue.shift();
        if (!request) throw new Error(`No pending fetch for ${path}`);
        request.resolve(new Response(JSON.stringify(payload), {
            status,
            headers: { "Content-Type": "application/json" },
        }));
    };

    window.fetch = (input, options = {}) => {
        const path = typeof input === "string" ? input : input.url;
        return new Promise((resolve) => {
            const queue = pending.get(path) || [];
            queue.push({ resolve, body: options.body || null });
            pending.set(path, queue);
        });
    };
})();
"""

_PROFILE: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
    "graduation_year": 2028,
    "highest_education": "master",
    "years_of_experience": 0.3,
    "skills": ["Python", "Agent"],
    "preferred_locations": ["上海"],
}
_JOB: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000002",
    "title": "Agent 研发工程师 (2027 届)",
    "company": "示例科技",
    "description": "工作地点：上海。面向 2027 届毕业生，要求本科及以上学历。",
    "constraints": {
        "minimum_education": "bachelor",
        "graduation_years": [2027],
        "minimum_years_of_experience": None,
        "locations": ["上海"],
    },
}
_EXTRACTION: dict[str, Any] = {
    "constraints": _JOB["constraints"],
    "evidence": {
        "graduation_years": [
            {
                "document_id": "00000000-0000-0000-0000-000000000003",
                "text": "2027 届",
                "start_offset": 3,
                "end_offset": 9,
            }
        ],
        "minimum_education": None,
        "minimum_years_of_experience": None,
        "locations": [],
    },
    "warnings": [],
}


@pytest.fixture
def workbench_page(page: Page, live_server_url: str) -> Iterator[Page]:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.add_init_script(script=_DEFERRED_FETCH_SCRIPT)
    page.goto(f"{live_server_url}/workbench")
    expect(page.locator("#run-state span:last-child")).to_have_text("等待输入")

    yield page

    assert page_errors == []


def _wait_for_request(page: Page, path: str) -> None:
    page.wait_for_function(
        "path => window.__pendingFetchCount(path) > 0",
        arg=path,
    )


def _resolve_request(page: Page, path: str, status: int, payload: Any) -> None:
    page.evaluate(
        "response => window.__resolveFetch(response)",
        {"path": path, "status": status, "payload": payload},
    )


def _save_example_entities(page: Page) -> None:
    page.locator("#load-example").click()

    page.locator("#profile-form button[type='submit']").click()
    _wait_for_request(page, "/profiles")
    _resolve_request(page, "/profiles", 201, _PROFILE)
    expect(page.locator("#profile-status")).to_have_text("已保存")

    page.locator("#job-form button[type='submit']").click()
    _wait_for_request(page, "/jobs")
    _resolve_request(page, "/jobs", 201, _JOB)
    expect(page.locator("#job-status")).to_have_text("已保存")
    expect(page.locator("#run-match")).to_be_enabled()


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        pytest.param(201, _PROFILE, id="stale-success"),
        pytest.param(500, {"detail": "旧保存请求失败"}, id="stale-failure"),
    ],
)
def test_stale_profile_save_response_cannot_restore_old_state(
    workbench_page: Page,
    status: int,
    payload: Any,
) -> None:
    page = workbench_page
    page.locator("#load-example").click()
    page.locator("#profile-form button[type='submit']").click()
    _wait_for_request(page, "/profiles")

    page.locator("#graduation-year").fill("2029")
    _resolve_request(page, "/profiles", status, payload)

    expect(page.locator("#profile-status")).to_have_text("未保存")
    expect(page.locator("#run-match")).to_be_disabled()
    expect(page.locator("#run-state span:last-child")).to_have_text("内容已修改，请保存")
    expect(page.locator("#profile-form button[type='submit']")).to_be_enabled()


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        pytest.param(201, _JOB, id="stale-success"),
        pytest.param(500, {"detail": "旧岗位保存请求失败"}, id="stale-failure"),
    ],
)
def test_stale_job_save_response_cannot_restore_old_state(
    workbench_page: Page,
    status: int,
    payload: Any,
) -> None:
    page = workbench_page
    page.locator("#load-example").click()
    page.locator("#job-form button[type='submit']").click()
    _wait_for_request(page, "/jobs")

    page.locator("#job-title").fill("已经修改的岗位")
    _resolve_request(page, "/jobs", status, payload)

    expect(page.locator("#job-status")).to_have_text("未保存")
    expect(page.locator("#run-match")).to_be_disabled()
    expect(page.locator("#run-state span:last-child")).to_have_text("内容已修改，请保存")
    expect(page.locator("#job-form button[type='submit']")).to_be_enabled()


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        pytest.param(200, _EXTRACTION, id="stale-success"),
        pytest.param(500, {"detail": "旧抽取请求失败"}, id="stale-failure"),
    ],
)
def test_stale_extraction_response_cannot_populate_changed_description(
    workbench_page: Page,
    status: int,
    payload: Any,
) -> None:
    page = workbench_page
    page.locator("#description").fill("面向 2027 届毕业生。")
    page.locator("#extract-constraints").click()
    _wait_for_request(page, "/jobs/parse")

    page.locator("#description").fill("描述已经改变，不应再应用旧抽取。")
    _resolve_request(page, "/jobs/parse", status, payload)

    expect(page.locator("#evidence-panel")).to_be_hidden()
    expect(page.locator("#required-years")).to_have_value("")
    expect(page.locator("#run-state span:last-child")).to_have_text("内容已修改，请保存")
    expect(page.locator("#extract-constraints")).to_have_text("从描述提取硬条件")


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        pytest.param(
            200,
            {"is_eligible": False, "reasons": ["graduation_year"]},
            id="stale-success",
        ),
        pytest.param(500, {"detail": "旧匹配请求失败"}, id="stale-failure"),
    ],
)
def test_stale_match_response_cannot_overwrite_edited_profile(
    workbench_page: Page,
    status: int,
    payload: Any,
) -> None:
    page = workbench_page
    _save_example_entities(page)
    page.locator("#run-match").click()
    _wait_for_request(page, "/matches")

    page.locator("#graduation-year").fill("2029")
    _resolve_request(page, "/matches", status, payload)

    expect(page.locator("#profile-status")).to_have_text("有修改")
    expect(page.locator("#result-title")).to_have_text("等待分析")
    expect(page.locator("#run-match")).to_be_disabled()
    expect(page.locator("#run-state span:last-child")).to_have_text("内容已修改，请重新保存")
