from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = [
    pytest.mark.browser,
    pytest.mark.only_browser("chromium"),
]

_EVENTS: list[dict[str, Any]] = [
    {
        "event_id": "00000000-0000-4000-8000-000000000002",
        "source_id": "nvidia-careers",
        "external_id": "JR2",
        "kind": "updated",
        "occurred_at": "2026-09-30T10:01:00Z",
        "title": "CUDA Intern",
        "source_url": "https://example.com/JR2",
        "saved": False,
        "ignored": False,
        "compare_later": False,
    },
    {
        "event_id": "00000000-0000-4000-8000-000000000001",
        "source_id": "nvidia-careers",
        "external_id": "JR1",
        "kind": "new",
        "occurred_at": "2026-09-30T10:00:00Z",
        "title": "AI Infra Intern",
        "source_url": "https://example.com/JR1",
        "saved": False,
        "ignored": False,
        "compare_later": False,
    },
]


def test_inbox_page_filters_and_updates_independent_flags(
    page: Page,
    live_server_url: str,
) -> None:
    events = [item.copy() for item in _EVENTS]
    updates: list[dict[str, bool]] = []

    def inbox(route: Route) -> None:
        if route.request.method == "PATCH":
            event_id = route.request.url.rsplit("/", 1)[-1]
            payload = cast(dict[str, bool], route.request.post_data_json)
            updates.append(payload)
            item = next(event for event in events if event["event_id"] == event_id)
            item.update(payload)
            route.fulfill(json=item)
            return
        parameters = parse_qs(urlparse(route.request.url).query)
        status = parameters.get("status", ["unhandled"])[0]
        kind = parameters.get("kind", [None])[0]
        filtered = [event for event in events if kind is None or event["kind"] == kind]
        if status == "unhandled":
            filtered = [
                event
                for event in filtered
                if not event["saved"] and not event["ignored"] and not event["compare_later"]
            ]
        elif status != "all":
            field = "compare_later" if status == "compare_later" else status
            filtered = [event for event in filtered if event[field]]
        route.fulfill(json=filtered)

    page.route("**/inbox/events**", inbox)
    page.goto(f"{live_server_url}/inbox")

    expect(page.locator(".inbox-item")).to_have_count(2)
    expect(page.locator("#inbox-total")).to_have_text("2 条动态")
    expect(page.locator(".inbox-item").first).to_contain_text("CUDA Intern")
    expect(page.get_by_text("已更新", exact=True)).to_be_visible()
    expect(page.locator(".inbox-kind-new")).to_have_text("新增")

    first = page.locator(".inbox-item").first
    first.get_by_role("checkbox", name="收藏", exact=True).check()
    expect(page.locator(".inbox-item")).to_have_count(1)
    assert updates == [{"saved": True}]

    page.locator("#inbox-status").select_option("saved")
    expect(page.locator(".inbox-item")).to_have_count(1)
    expect(page.locator(".inbox-item")).to_contain_text("CUDA Intern")
    expect(page.get_by_role("checkbox", name="收藏", exact=True)).to_be_checked()
    page.get_by_role("checkbox", name="待比较", exact=True).check()
    assert updates[-1] == {"compare_later": True}

    page.locator("#inbox-kind").select_option("new")
    expect(page.locator(".inbox-item")).to_have_count(0)


def test_mobile_inbox_has_no_horizontal_overflow(page: Page, live_server_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.route("**/inbox/events**", lambda route: route.fulfill(json=_EVENTS))

    page.goto(f"{live_server_url}/inbox")

    expect(page.locator(".inbox-item")).to_have_count(2)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") is True
    expect(page.get_by_role("link", name="机会首页")).to_be_in_viewport()
