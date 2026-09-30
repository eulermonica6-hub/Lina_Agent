import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from lina_agent.domain.job_discovery import JobSearchRequest, JobSourceStatus, JobType
from lina_agent.infrastructure.job_sources.nvidia_workday import NvidiaWorkdayJobSource

_NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
_FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "nvidia_workday_jobs.json").read_text(
        encoding="utf-8"
    )
)


def _fixture_transport(requests: list[dict[str, Any]]) -> httpx.MockTransport:
    postings = cast(list[dict[str, Any]], _FIXTURE["jobPostings"])

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            posting = next(
                item for item in postings if cast(str, item["externalPath"]) in request.url.path
            )
            external_id = cast(list[str], posting["bulletFields"])[0]
            return httpx.Response(
                200,
                json={
                    "jobPostingInfo": {
                        "title": posting["title"],
                        "jobDescription": (
                            f"<p>Build &amp; <b>test</b> {posting['title']}.</p>"
                            "<ul><li>Python</li><li>AI systems</li></ul>"
                        ),
                        "location": posting["locationsText"],
                        "postedOn": posting["postedOn"],
                        "startDate": "2026-09-30",
                        "timeType": "Full time",
                        "jobReqId": external_id,
                    }
                },
                request=request,
            )
        payload = cast(dict[str, Any], json.loads(request.content))
        requests.append(payload)
        offset = cast(int, payload["offset"])
        limit = cast(int, payload["limit"])
        return httpx.Response(
            200,
            json={
                "total": len(postings),
                "jobPostings": postings[offset : offset + limit],
            },
            request=request,
        )

    return httpx.MockTransport(respond)


def test_nvidia_source_paginates_and_maps_official_jobs() -> None:
    requests: list[dict[str, Any]] = []
    source = NvidiaWorkdayJobSource(
        transport=_fixture_transport(requests),
        clock=lambda: _NOW,
        page_size=2,
    )

    result = asyncio.run(
        source.search(
            JobSearchRequest(
                companies=("NVIDIA",),
                locations=("上海",),
                job_types=(JobType.INTERNSHIP, JobType.CAMPUS),
                max_results=5,
            )
        )
    )

    assert result.status is JobSourceStatus.SUCCESS
    assert result.error_code is None
    assert [request["offset"] for request in requests] == [0, 2, 4, 6]
    assert {lead.external_id for lead in result.leads} == {
        "JR2024692",
        "JR2022870",
        "JR2026402",
        "JR2000002",
        "JR2023652",
    }
    assert {lead.job_type for lead in result.leads} == {
        JobType.INTERNSHIP,
        JobType.CAMPUS,
    }
    assert all(lead.locations == ("上海",) for lead in result.leads)
    assert all(lead.verification_status.value == "live" for lead in result.leads)
    assert all(
        lead.source_url.startswith("https://nvidia.wd5.myworkdayjobs.com/") for lead in result.leads
    )
    assert result.leads[0].direction == "GPU / CUDA"
    assert result.leads[-1].direction == "Software Engineering"
    assert result.leads[0].normalized_description.startswith("Build & test")
    assert "<" not in result.leads[0].normalized_description
    assert result.leads[0].content_fingerprint is not None
    assert len(result.leads[0].content_fingerprint) == 64
    cuda = next(lead for lead in result.leads if lead.external_id == "JR2000002")
    assert cuda.direction == "AI / Machine Learning"
    assert {"CUDA", "Machine Learning", "Software Engineering"} <= set(cuda.highlights)


def test_nvidia_source_uses_query_and_filters_results_locally() -> None:
    requests: list[dict[str, Any]] = []
    source = NvidiaWorkdayJobSource(
        transport=_fixture_transport(requests),
        clock=lambda: _NOW,
        page_size=2,
    )

    result = asyncio.run(source.search(JobSearchRequest(query="Test Development", max_results=10)))

    assert [lead.external_id for lead in result.leads] == ["JR2023652"]
    assert all(request["searchText"] == "Shanghai Test Development" for request in requests)


def test_nvidia_source_stops_after_reaching_result_limit() -> None:
    requests: list[dict[str, Any]] = []
    source = NvidiaWorkdayJobSource(
        transport=_fixture_transport(requests),
        clock=lambda: _NOW,
        page_size=2,
    )

    result = asyncio.run(source.search(JobSearchRequest(max_results=1)))

    assert [lead.external_id for lead in result.leads] == ["JR2024692"]
    assert len(requests) == 1


def test_nvidia_full_capture_ignores_user_limit_and_keeps_multi_location_jobs() -> None:
    requests: list[dict[str, Any]] = []
    source = NvidiaWorkdayJobSource(
        transport=_fixture_transport(requests),
        clock=lambda: _NOW,
        page_size=2,
        full_capture=True,
    )

    result = asyncio.run(source.search(JobSearchRequest(query="no-match", max_results=1)))

    assert result.status is JobSourceStatus.SUCCESS
    assert len(result.leads) == 6
    assert all(request["searchText"] == "Shanghai" for request in requests)
    multi_location = next(lead for lead in result.leads if lead.external_id == "JR2019975")
    assert multi_location.locations == ("北京", "上海")


def test_nvidia_source_skips_unsupported_company_and_location_without_network() -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected request: {request.url}")

    source = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(unexpected),
        clock=lambda: _NOW,
    )

    company = asyncio.run(source.search(JobSearchRequest(companies=("Apple",))))
    location = asyncio.run(source.search(JobSearchRequest(locations=("北京",))))

    assert company.status is JobSourceStatus.SUCCESS
    assert company.leads == ()
    assert location.status is JobSourceStatus.SUCCESS
    assert location.leads == ()


@pytest.mark.parametrize(
    ("status_code", "expected_status", "error_code"),
    [
        (403, JobSourceStatus.BLOCKED, "http_403"),
        (429, JobSourceStatus.RATE_LIMITED, "http_429"),
        (500, JobSourceStatus.FAILED, "http_500"),
    ],
)
def test_nvidia_source_classifies_http_errors(
    status_code: int,
    expected_status: JobSourceStatus,
    error_code: str,
) -> None:
    source = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code, request=request)),
        clock=lambda: _NOW,
    )

    result = asyncio.run(source.search(JobSearchRequest()))

    assert result.status is expected_status
    assert result.error_code == error_code


@pytest.mark.parametrize(
    "malformed_payload",
    [None, {"total": 1}],
)
def test_nvidia_source_reports_structure_changes(
    malformed_payload: dict[str, int] | None,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if malformed_payload is None:
            return httpx.Response(200, text="not-json", request=request)
        return httpx.Response(200, json=malformed_payload, request=request)

    source = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(respond),
        clock=lambda: _NOW,
    )

    result = asyncio.run(source.search(JobSearchRequest()))

    assert result.status is JobSourceStatus.STRUCTURE_CHANGED
    assert result.error_code == "invalid_workday_payload"


def test_nvidia_source_handles_empty_pages_and_network_errors() -> None:
    empty = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"total": 0, "jobPostings": []},
                request=request,
            )
        ),
        clock=lambda: _NOW,
        page_size=100,
    )

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    offline = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(fail),
        clock=lambda: _NOW,
    )

    empty_result = asyncio.run(empty.search(JobSearchRequest()))
    offline_result = asyncio.run(offline.search(JobSearchRequest()))

    assert empty_result.status is JobSourceStatus.SUCCESS
    assert empty_result.leads == ()
    assert offline_result.status is JobSourceStatus.FAILED
    assert offline_result.error_code == "network_error"


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_status", "error_code"),
    [
        (403, None, JobSourceStatus.PARTIAL, "detail_http_403"),
        (
            200,
            {"jobPostingInfo": {"title": "Missing fields"}},
            JobSourceStatus.STRUCTURE_CHANGED,
            "invalid_workday_detail",
        ),
    ],
)
def test_nvidia_source_rejects_incomplete_detail_batches(
    status_code: int,
    payload: dict[str, object] | None,
    expected_status: JobSourceStatus,
    error_code: str,
) -> None:
    posting = cast(dict[str, Any], _FIXTURE["jobPostings"][0])

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"total": 1, "jobPostings": [posting]},
                request=request,
            )
        if payload is None:
            return httpx.Response(status_code, request=request)
        return httpx.Response(status_code, json=payload, request=request)

    source = NvidiaWorkdayJobSource(
        transport=httpx.MockTransport(respond),
        clock=lambda: _NOW,
    )

    result = asyncio.run(source.search(JobSearchRequest()))

    assert result.status is expected_status
    assert result.error_code == error_code
