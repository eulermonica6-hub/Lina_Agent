import pytest

from lina_agent.infrastructure.sandbox import (
    PythonSandbox,
    RepairLoop,
    SandboxValidationError,
)


def test_sandbox_runs_without_project_environment() -> None:
    result = PythonSandbox().execute("print('ok')")

    assert result.success is True
    assert result.stdout.strip() == "ok"


def test_sandbox_rejects_shell_and_file_access() -> None:
    with pytest.raises(SandboxValidationError):
        PythonSandbox().execute("import subprocess")
    with pytest.raises(SandboxValidationError):
        PythonSandbox().execute("open('secret.txt')")


def test_repair_loop_retries_candidate_until_success() -> None:
    result = RepairLoop().run(
        "raise RuntimeError('broken')",
        ("print('repaired')",),
    )

    assert result.success is True
    assert result.source == "print('repaired')"
    assert len(result.attempts) == 2
    assert result.attempts[0].result.success is False
    assert result.attempts[1].result.stdout.strip() == "repaired"


def test_repair_loop_is_bounded() -> None:
    result = RepairLoop(max_attempts=2).run(
        "raise RuntimeError('one')",
        ("raise RuntimeError('two')", "print('not reached')"),
    )

    assert result.success is False
    assert len(result.attempts) == 2


def test_sandbox_timeout_is_reported() -> None:
    result = PythonSandbox(timeout_seconds=0.1).execute("while True: pass")

    assert result.success is False
    assert result.timed_out is True
    assert "timed out" in result.stderr
