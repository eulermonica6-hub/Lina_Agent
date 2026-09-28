from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from lina_agent.domain.job_discovery import (
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
)
from lina_agent.domain.weekly_monitoring import MonitoredJobSource


class OfficialCareersPageProbe:
    def __init__(
        self,
        source: MonitoredJobSource,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.source_id = source.source_id
        self._source = source
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        del request
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                follow_redirects=True,
                timeout=20,
                headers={"User-Agent": "Lina-Career-Agent/weekly-monitor"},
            ) as client:
                response = await client.get(self._source.url)
        except httpx.HTTPError:
            return self._result(JobSourceStatus.FAILED, "network_error")

        if response.status_code == 429:
            return self._result(JobSourceStatus.RATE_LIMITED, "http_429")
        if response.status_code in {401, 403}:
            return self._result(JobSourceStatus.BLOCKED, f"http_{response.status_code}")
        if response.status_code >= 400:
            return self._result(JobSourceStatus.FAILED, f"http_{response.status_code}")
        if not response.text.strip():
            return self._result(JobSourceStatus.STRUCTURE_CHANGED, "empty_page")
        return self._result(JobSourceStatus.PARTIAL, "listing_parser_pending")

    def _result(self, status: JobSourceStatus, error_code: str) -> JobSourceResult:
        return JobSourceResult(
            source_id=self.source_id,
            status=status,
            fetched_at=self._clock(),
            error_code=error_code,
        )
