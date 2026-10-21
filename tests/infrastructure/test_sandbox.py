import pytest

from lina_agent.infrastructure import sandbox as sandbox_module
from lina_agent.infrastructure.sandbox import (
    PythonSandbox,
    RepairLoop,
    SandboxExecutionError,
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


def test_sandbox_accepts_allowlisted_imports() -> None:
    result = PythonSandbox().execute("import json\nprint(json.dumps({'ok': True}))")

    assert result.success is True
    assert result.stdout.strip() == '{"ok": true}'


def test_source_validation_reports_empty_large_and_invalid_source() -> None:
    with pytest.raises(SandboxValidationError, match="empty"):
        PythonSandbox().execute(" ")
    with pytest.raises(SandboxValidationError, match="size"):
        PythonSandbox().execute("x = '" + ("a" * 100_001) + "'")
    with pytest.raises(SandboxValidationError, match="syntax"):
        PythonSandbox().execute("if:")


def test_sandbox_rejects_invalid_configuration_and_process_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="timeout"):
        PythonSandbox(timeout_seconds=0)
    with pytest.raises(ValueError, match="output"):
        PythonSandbox(max_output_bytes=0)
    with pytest.raises(ValueError, match="max_attempts"):
        RepairLoop(max_attempts=4)

    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise OSError("unavailable")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fail_to_start)
    with pytest.raises(SandboxExecutionError, match="start"):
        PythonSandbox().execute("print('ok')")


def test_sandbox_truncates_output_and_handles_bytes_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = PythonSandbox(max_output_bytes=3).execute("print('abcdef')")
    assert result.stdout.endswith("[output truncated]")

    class Timeout:
        stdout = b"out"
        stderr = b"err"

    def timeout(*args: object, **kwargs: object) -> None:
        raise sandbox_module.subprocess.TimeoutExpired(
            "python", 1, output=Timeout.stdout, stderr=Timeout.stderr
        )

    monkeypatch.setattr(sandbox_module.subprocess, "run", timeout)
    result = PythonSandbox().execute("print('ok')")
    assert result.stdout == "out"
    assert "err" in result.stderr

    def timeout_without_output(*args: object, **kwargs: object) -> None:
        raise sandbox_module.subprocess.TimeoutExpired("python", 1)

    monkeypatch.setattr(sandbox_module.subprocess, "run", timeout_without_output)
    result = PythonSandbox().execute("print('ok')")
    assert result.stdout == ""


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


def test_repair_loop_validates_repair_candidates_before_execution() -> None:
    with pytest.raises(SandboxValidationError, match="allowlist"):
        RepairLoop().run("print('ok')", ("import subprocess",))


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
