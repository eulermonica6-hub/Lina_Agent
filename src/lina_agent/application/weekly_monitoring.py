from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from lina_agent.application.job_discovery import JobDiscoveryService, JobSourceAdapter
from lina_agent.domain.job_discovery import JobSearchRequest, JobSourceStatus
from lina_agent.domain.weekly_monitoring import (
    MonitoredJobSource,
    MonitoringRunStatus,
    WeeklyMonitoringRun,
)

_FAILURE_STATUSES = {
    JobSourceStatus.RATE_LIMITED,
    JobSourceStatus.BLOCKED,
    JobSourceStatus.STRUCTURE_CHANGED,
    JobSourceStatus.FAILED,
}


class WeeklyMonitoringService:
    def __init__(
        self,
        sources: tuple[JobSourceAdapter, ...],
        *,
        monitored_sources: tuple[MonitoredJobSource, ...] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._discovery = JobDiscoveryService(sources)
        self._monitored_sources = monitored_sources
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self._discovery.source_ids

    async def run(self, week_start: date | None = None) -> WeeklyMonitoringRun:
        started_at = self._clock()
        effective_week_start = week_start or (
            started_at.date() - timedelta(days=started_at.weekday())
        )
        result = await self._discovery.search(JobSearchRequest(max_results=100))
        statuses = tuple(source.status for source in result.sources)
        if statuses and all(status is JobSourceStatus.SUCCESS for status in statuses):
            run_status = MonitoringRunStatus.COMPLETE
        elif all(status in _FAILURE_STATUSES for status in statuses):
            run_status = MonitoringRunStatus.FAILED
        else:
            run_status = MonitoringRunStatus.PARTIAL

        return WeeklyMonitoringRun(
            run_id=f"lina-weekly:{effective_week_start.isoformat()}",
            week_start=effective_week_start,
            started_at=started_at,
            completed_at=self._clock(),
            status=run_status,
            monitored_sources=self._monitored_sources,
            sources=result.sources,
            leads=result.leads,
        )
