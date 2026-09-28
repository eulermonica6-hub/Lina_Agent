import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from lina_agent.domain.job_discovery import JobSearchRequest, JobSourceStatus
from lina_agent.infrastructure.job_sources.official_probe import OfficialCareersPageProbe
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES

_NOW = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)


def test_registry_contains_all_seven_requested_official_sources() -> None:
    requested_sources = {
        ("腾讯", "tencent-careers"),
        ("字节跳动", "bytedance-careers"),
        ("阿里巴巴", "alibaba-careers"),
        ("蚂蚁集团", "ant-group-careers"),
        ("Microsoft", "microsoft-careers"),
        ("Amazon", "amazon-shanghai"),
        ("Meltwater", "meltwater-careers"),
    }
    actual_sources = {(source.company, source.source_id) for source in MONITORED_JOB_SOURCES}

    assert requested_sources <= actual_sources
    assert all(source.url.startswith("https://") for source in MONITORED_JOB_SOURCES)
    assert all(source.keywords for source in MONITORED_JOB_SOURCES)


@pytest.mark.parametrize(
    ("status_code", "expected_status", "error_code"),
    [
        (200, JobSourceStatus.PARTIAL, "listing_parser_pending"),
        (403, JobSourceStatus.BLOCKED, "http_403"),
        (429, JobSourceStatus.RATE_LIMITED, "http_429"),
        (500, JobSourceStatus.FAILED, "http_500"),
    ],
)
def test_probe_classifies_http_statuses(
    status_code: int,
    expected_status: JobSourceStatus,
    error_code: str,
) -> None:
    source = MONITORED_JOB_SOURCES[0]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, text="careers page", request=request)
    )
    probe = OfficialCareersPageProbe(source, transport=transport, clock=lambda: _NOW)

    result = asyncio.run(probe.search(JobSearchRequest()))

    assert result.source_id == "tencent-careers"
    assert result.status is expected_status
    assert result.error_code == error_code
    assert result.fetched_at == _NOW
    assert result.leads == ()


def test_probe_reports_empty_page_and_network_error() -> None:
    source = MONITORED_JOB_SOURCES[0]
    empty = OfficialCareersPageProbe(
        source,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="", request=request)
        ),
        clock=lambda: _NOW,
    )

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    offline = OfficialCareersPageProbe(
        source,
        transport=httpx.MockTransport(fail),
        clock=lambda: _NOW,
    )

    empty_result = asyncio.run(empty.search(JobSearchRequest()))
    offline_result = asyncio.run(offline.search(JobSearchRequest()))

    assert empty_result.status is JobSourceStatus.STRUCTURE_CHANGED
    assert empty_result.error_code == "empty_page"
    assert offline_result.status is JobSourceStatus.FAILED
    assert offline_result.error_code == "network_error"
