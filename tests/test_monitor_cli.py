from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lina_agent.application.weekly_monitoring import WeeklyMonitoringService
from lina_agent.cli.monitor import build_monitoring_service, main
from lina_agent.domain.weekly_monitoring import MonitoringRunStatus, WeeklyMonitoringRun


class StubMonitoringService:
    async def run(self, week_start: date | None = None) -> WeeklyMonitoringRun:
        effective_week = week_start or date(2026, 9, 28)
        timestamp = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
        return WeeklyMonitoringRun(
            run_id=f"lina-weekly:{effective_week.isoformat()}",
            week_start=effective_week,
            started_at=timestamp,
            completed_at=timestamp,
            status=MonitoringRunStatus.PARTIAL,
            sources=(),
            leads=(),
        )


def test_monitor_cli_writes_lina_weekly_json(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "weekly-monitor.json"

    main(
        ["--week-start", "2026-09-28", "--output", str(output)],
        service=StubMonitoringService(),
    )

    payload = output.read_text(encoding="utf-8")
    assert '"agent_name": "Lina"' in payload
    assert '"run_id": "lina-weekly:2026-09-28"' in payload
    assert '"status": "partial"' in payload


def test_monitor_cli_prints_json_and_builds_default_service(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--week-start", "2026-09-28"], service=StubMonitoringService())

    output = capsys.readouterr().out
    assert '"agent_name": "Lina"' in output
    service = build_monitoring_service()
    assert isinstance(service, WeeklyMonitoringService)
    assert service.source_ids.count("nvidia-careers") == 1
    assert "nvidia-careers" in service.source_ids
