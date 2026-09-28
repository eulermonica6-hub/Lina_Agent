import argparse
import asyncio
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Protocol

from lina_agent.application.weekly_monitoring import WeeklyMonitoringService
from lina_agent.domain.weekly_monitoring import WeeklyMonitoringRun
from lina_agent.infrastructure.job_sources.official_probe import OfficialCareersPageProbe
from lina_agent.infrastructure.job_sources.registry import MONITORED_JOB_SOURCES


class MonitoringRunner(Protocol):
    async def run(self, week_start: date | None = None) -> WeeklyMonitoringRun: ...


def build_monitoring_service() -> WeeklyMonitoringService:
    sources = tuple(OfficialCareersPageProbe(source) for source in MONITORED_JOB_SOURCES)
    return WeeklyMonitoringService(sources, monitored_sources=MONITORED_JOB_SOURCES)


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
