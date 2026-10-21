from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

MAX_SOURCE_BYTES: Final = 100_000
MAX_OUTPUT_BYTES: Final = 32_000
MAX_REPAIR_ATTEMPTS: Final = 3
DEFAULT_TIMEOUT_SECONDS: Final = 5.0
_ALLOWED_IMPORTS: Final = frozenset(
    {
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "functools",
        "itertools",
        "json",
        "math",
        "re",
        "statistics",
        "string",
        "typing",
    }
)
_BLOCKED_CALLS: Final = frozenset({"__import__", "compile", "eval", "exec", "open", "input"})


class SandboxValidationError(ValueError):
    """Raised when source is outside the intentionally small execution contract."""


class SandboxExecutionError(RuntimeError):
    """Raised when the sandbox process cannot be started or managed."""


@dataclass(frozen=True, slots=True)
class SandboxResult:
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    attempt: int
    result: SandboxResult


@dataclass(frozen=True, slots=True)
class RepairLoopResult:
    success: bool
    source: str
    attempts: tuple[RepairAttempt, ...]


def validate_source(source: str) -> None:
    if not source.strip():
        raise SandboxValidationError("source must not be empty")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SandboxValidationError("source exceeds the sandbox size limit")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise SandboxValidationError(f"source has invalid syntax: {error.msg}") from error

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name.split(".", 1)[0] for alias in node.names]
            imported = ([module.split(".", 1)[0]] if module else []) + names
            if any(name not in _ALLOWED_IMPORTS for name in imported):
                raise SandboxValidationError(
                    "source imports a module outside the sandbox allowlist"
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _BLOCKED_CALLS
        ):
            raise SandboxValidationError(f"source uses blocked call: {node.func.id}")


class PythonSandbox:
    """Run small deterministic validation programs in a disposable subprocess.

    This is a process sandbox for generated checks, not a hostile-code isolation
    boundary. It deliberately omits shell access, network configuration, and
    project files from the execution contract.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def execute(self, source: str) -> SandboxResult:
        validate_source(source)
        with tempfile.TemporaryDirectory(prefix="lina-sandbox-") as directory:
            script = Path(directory) / "main.py"
            script.write_text(source, encoding="utf-8")
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            }
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(script)],
                    cwd=directory,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                return SandboxResult(
                    success=False,
                    exit_code=None,
                    stdout=_truncate(error.stdout, self.max_output_bytes),
                    stderr=_truncate(error.stderr, self.max_output_bytes) + "\nexecution timed out",
                    timed_out=True,
                )
            except OSError as error:
                raise SandboxExecutionError("failed to start sandbox process") from error
        return SandboxResult(
            success=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=_truncate(completed.stdout, self.max_output_bytes),
            stderr=_truncate(completed.stderr, self.max_output_bytes),
        )


class RepairLoop:
    def __init__(
        self, sandbox: PythonSandbox | None = None, *, max_attempts: int = MAX_REPAIR_ATTEMPTS
    ) -> None:
        if max_attempts < 1 or max_attempts > MAX_REPAIR_ATTEMPTS:
            raise ValueError(f"max_attempts must be between 1 and {MAX_REPAIR_ATTEMPTS}")
        self.sandbox = sandbox or PythonSandbox()
        self.max_attempts = max_attempts

    def run(self, source: str, repair_candidates: tuple[str, ...] = ()) -> RepairLoopResult:
        candidates = repair_candidates[: self.max_attempts - 1]
        validate_source(source)
        for candidate in candidates:
            validate_source(candidate)
        current = source
        attempts: list[RepairAttempt] = []
        for attempt_number in range(1, self.max_attempts + 1):
            result = self.sandbox.execute(current)
            attempts.append(RepairAttempt(attempt=attempt_number, result=result))
            if result.success:
                return RepairLoopResult(success=True, source=current, attempts=tuple(attempts))
            if attempt_number > len(candidates):
                break
            current = candidates[attempt_number - 1]
        return RepairLoopResult(success=False, source=current, attempts=tuple(attempts))


def _truncate(value: str | bytes | None, limit: int) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[output truncated]"
