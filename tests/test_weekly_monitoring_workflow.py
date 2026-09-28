from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def test_weekly_monitor_workflow_has_schedule_manual_trigger_and_artifact() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/weekly-job-monitor.yml").read_text(
        encoding="utf-8"
    )

    assert "name: Lina Weekly Job Monitor" in workflow
    assert "schedule:" in workflow
    assert 'cron: "0 1 * * 1"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "uv run --locked lina-monitor" in workflow
    assert "weekly-monitor.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
