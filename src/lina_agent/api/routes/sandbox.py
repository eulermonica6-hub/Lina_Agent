from fastapi import APIRouter
from pydantic import BaseModel, Field

from lina_agent.infrastructure.sandbox import (
    MAX_REPAIR_ATTEMPTS,
    PythonSandbox,
    RepairLoop,
    SandboxValidationError,
)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class SandboxRequest(BaseModel):
    source: str = Field(min_length=1, max_length=100_000)
    repair_candidates: tuple[str, ...] = Field(default=(), max_length=MAX_REPAIR_ATTEMPTS - 1)
    timeout_seconds: float = Field(default=5.0, gt=0, le=10.0)


class SandboxAttemptResponse(BaseModel):
    attempt: int
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


class SandboxResponse(BaseModel):
    success: bool
    final_source: str
    attempts: tuple[SandboxAttemptResponse, ...]


@router.post("/runs", response_model=SandboxResponse)
def run_sandbox(request: SandboxRequest) -> SandboxResponse:
    try:
        result = RepairLoop(PythonSandbox(timeout_seconds=request.timeout_seconds)).run(
            request.source,
            request.repair_candidates,
        )
    except SandboxValidationError as error:
        return SandboxResponse(
            success=False,
            final_source=request.source,
            attempts=(
                SandboxAttemptResponse(
                    attempt=1,
                    success=False,
                    exit_code=None,
                    stdout="",
                    stderr=str(error),
                    timed_out=False,
                ),
            ),
        )
    return SandboxResponse(
        success=result.success,
        final_source=result.source,
        attempts=tuple(
            SandboxAttemptResponse(
                attempt=attempt.attempt,
                success=attempt.result.success,
                exit_code=attempt.result.exit_code,
                stdout=attempt.result.stdout,
                stderr=attempt.result.stderr,
                timed_out=attempt.result.timed_out,
            )
            for attempt in result.attempts
        ),
    )
