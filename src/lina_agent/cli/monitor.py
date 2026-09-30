import argparse
import asyncio
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Protocol

from lina_agent.application.job_change_tracking import JobChangeTrackingService
from lina_agent.application.weekly_monitoring import WeeklyMonitoringService
from lina_agent.config import Settings, get_settings
from lina_agent.domain.weekly_monitoring import WeeklyMonitoringRun
from lina_agent.infrastructure.job_sources.nvidia_workday import NvidiaWorkdayJobSource
from lina_agent.infrastructure.job_sources.official_probe import OfficialCareersPageProbe
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES
from lina_agent.infrastructure.repositories.memory import InMemoryJobChangeRepository
from lina_agent.infrastructure.repositories.sqlite import SQLiteJobChangeRepository


class MonitoringRunner(Protocol):
    async def run(self, week_start: date | None = None) -> WeeklyMonitoringRun: ...


def build_monitoring_service(settings: Settings | None = None) -> WeeklyMonitoringService:
    app_settings = settings or get_settings()
    sources = tuple(
        NvidiaWorkdayJobSource(full_capture=True)
        if source.source_id == "nvidia-careers"
        else OfficialCareersPageProbe(source)
        for source in MONITORED_JOB_SOURCES
    )
    repository = (
        InMemoryJobChangeRepository()
        if app_settings.database_path is None
        else SQLiteJobChangeRepository(app_settings.database_path)
    )
    return WeeklyMonitoringService(
        sources,
        monitored_sources=MONITORED_JOB_SOURCES,
        change_tracker=JobChangeTrackingService(repository),
        tracked_source_ids=("nvidia-careers",),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    service: MonitoringRunner | None = None,
) -> None:
    parser = argparse.ArgumentParser(description="Lina 每周检查官方招聘入口并输出来源健康报告。")
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        help="监控周的周一日期，格式 YYYY-MM-DD；默认使用当前周",
    )
    parser.add_argument("--output", type=Path, help="JSON 报告输出路径；省略时输出到 stdout")
    arguments = parser.parse_args(argv)

    run = asyncio.run((service or build_monitoring_service()).run(arguments.week_start))
    payload = run.model_dump_json(indent=2)
    if arguments.output is None:
        print(payload)
        return

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(payload + "\n", encoding="utf-8")
    print(f"Lina weekly monitor report: {arguments.output}")
