from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from lina_agent.domain.job_changes import JobCaptureBatch, JobChangeEvent
from lina_agent.domain.job_discovery import CompanyPool, JobLead, JobSourceResult
from lina_agent.domain.models import DomainModel


class MonitoringRunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class MonitoredJobSource(DomainModel):
    source_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    keywords: tuple[str, ...] = Field(min_length=1)
    pool: CompanyPool = CompanyPool.DOMESTIC_MAJOR
    regions: tuple[str, ...] = ()
    why_watch: str = ""
    market_cap_scope: Literal["domestic_tech", "global_tech"] | None = None
    market_cap_rank: int | None = Field(default=None, ge=1, le=10)
    market_cap_as_of: date | None = None
    market_cap_source: str | None = Field(default=None, pattern=r"^https://")


class WeeklyMonitoringRun(DomainModel):
    agent_name: Literal["Lina"] = "Lina"
    run_id: str = Field(min_length=1)
    week_start: date
    started_at: datetime
    completed_at: datetime
    status: MonitoringRunStatus
    monitored_sources: tuple[MonitoredJobSource, ...] = ()
    sources: tuple[JobSourceResult, ...]
    leads: tuple[JobLead, ...]
    capture_batches: tuple[JobCaptureBatch, ...] = ()
    change_events: tuple[JobChangeEvent, ...] = ()
