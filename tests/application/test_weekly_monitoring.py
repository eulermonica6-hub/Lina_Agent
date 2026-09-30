import asyncio
from datetime import UTC, date, datetime

from lina_agent.application.job_change_tracking import JobChangeTrackingService
from lina_agent.application.job_discovery import JobSourceAdapter
from lina_agent.application.weekly_monitoring import WeeklyMonitoringService
from lina_agent.domain.job_changes import JobChangeKind
from lina_agent.domain.job_discovery import (
    JobLead,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobType,
    JobVerificationStatus,
)
from lina_agent.domain.weekly_monitoring import MonitoredJobSource, MonitoringRunStatus
from lina_agent.infrastructure.repositories.memory import InMemoryJobChangeRepository

_NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


class FakeSource(JobSourceAdapter):
    def __init__(
        self,
        source_id: str,
        status: JobSourceStatus,
        leads: tuple[JobLead, ...] = (),
    ) -> None:
        self.source_id = source_id
        self._status = status
        self._leads = leads

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        return JobSourceResult(
            source_id=self.source_id,
            status=self._status,
            fetched_at=_NOW,
            leads=self._leads,
            error_code=None if self._status is JobSourceStatus.SUCCESS else "test_status",
        )


def test_weekly_run_has_lina_identity_monday_key_and_partial_status() -> None:
    monitored_source = MonitoredJobSource(
        source_id="healthy",
        company="Example",
        url="https://example.com/careers",
        keywords=("Agent", "RAG"),
    )
    service = WeeklyMonitoringService(
        (
            FakeSource("healthy", JobSourceStatus.SUCCESS),
            FakeSource("pending", JobSourceStatus.PARTIAL),
        ),
        monitored_sources=(monitored_source,),
        clock=lambda: _NOW,
    )

    run = asyncio.run(service.run())

    assert run.agent_name == "Lina"
    assert run.week_start == date(2026, 9, 28)
    assert run.run_id == "lina-weekly:2026-09-28"
    assert run.status is MonitoringRunStatus.PARTIAL
    assert [source.source_id for source in run.sources] == ["healthy", "pending"]
    assert run.monitored_sources == (monitored_source,)


def test_weekly_run_reports_complete_and_failed_states() -> None:
    complete = WeeklyMonitoringService(
        (FakeSource("healthy", JobSourceStatus.SUCCESS),),
        clock=lambda: _NOW,
    )
    failed = WeeklyMonitoringService(
        (
            FakeSource("blocked", JobSourceStatus.BLOCKED),
            FakeSource("failed", JobSourceStatus.FAILED),
        ),
        clock=lambda: _NOW,
    )

    complete_run = asyncio.run(complete.run(week_start=date(2026, 9, 21)))
    failed_run = asyncio.run(failed.run())

    assert complete_run.status is MonitoringRunStatus.COMPLETE
    assert complete_run.run_id == "lina-weekly:2026-09-21"
    assert failed_run.status is MonitoringRunStatus.FAILED


def test_weekly_run_tracks_only_complete_configured_source_batches() -> None:
    repository = InMemoryJobChangeRepository()
    tracker = JobChangeTrackingService(repository)
    baseline_service = WeeklyMonitoringService(
        (FakeSource("nvidia-careers", JobSourceStatus.SUCCESS, (_lead("JR1"),)),),
        change_tracker=tracker,
        tracked_source_ids=("nvidia-careers",),
        clock=lambda: _NOW,
    )

    baseline = asyncio.run(baseline_service.run())
    partial = asyncio.run(
        WeeklyMonitoringService(
            (
                FakeSource(
                    "nvidia-careers",
                    JobSourceStatus.PARTIAL,
                    (_lead("JR2"),),
                ),
                FakeSource("other", JobSourceStatus.SUCCESS, (_lead("JR3", "other"),)),
            ),
            change_tracker=tracker,
            tracked_source_ids=("nvidia-careers",),
            clock=lambda: _NOW,
        ).run()
    )
    changed = asyncio.run(
        WeeklyMonitoringService(
            (FakeSource("nvidia-careers", JobSourceStatus.SUCCESS, (_lead("JR2"),)),),
            change_tracker=tracker,
            tracked_source_ids=("nvidia-careers",),
            clock=lambda: _NOW,
        ).run()
    )

    assert baseline.capture_batches[0].baseline is True
    assert baseline.change_events == ()
    assert partial.capture_batches == ()
    assert partial.change_events == ()
    assert {event.kind for event in changed.change_events} == {
        JobChangeKind.NEW,
        JobChangeKind.CLOSED,
    }


def _lead(external_id: str, source_id: str = "nvidia-careers") -> JobLead:
    return JobLead(
        lead_id=f"{source_id}:{external_id}",
        deduplication_key=f"{source_id}:{external_id}",
        source_id=source_id,
        external_id=external_id,
        company="NVIDIA",
        title="AI Intern",
        job_type=JobType.INTERNSHIP,
        locations=("上海",),
        direction="AI / Machine Learning",
        source_url=f"https://example.com/{external_id}",
        captured_at=_NOW,
        verification_status=JobVerificationStatus.LIVE,
    )
