from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Base64Bytes, BaseModel, Field, model_validator

from lina_agent.api.dependencies import get_agent_run_repository
from lina_agent.application.agent_run_snapshot import (
    AgentRunRequestSnapshot,
    AgentRunSnapshot,
    create_agent_run_snapshot,
)
from lina_agent.application.career_agent import CareerAgentRun, CareerMatchAgent
from lina_agent.application.repositories import AgentRunSnapshotRepository
from lina_agent.domain.career_matching import (
    CandidateAvailabilityConfirmation,
    CandidateDirectionPreferenceConfirmation,
)
from lina_agent.domain.job_catalog import JobCatalogParseError
from lina_agent.infrastructure.document_loader import DocumentLoadError, LocalDocumentLoader
from lina_agent.infrastructure.llm_career_planner import LLMCareerPlanner

router = APIRouter(prefix="/agent", tags=["agent"])


class EncodedDocument(BaseModel):
    filename: str = Field(min_length=1)
    content: Base64Bytes


class CareerAgentRequest(BaseModel):
    resume: EncodedDocument
    job_catalog: EncodedDocument
    top_k: int = Field(default=5, ge=1, le=50)
    include_inactive: bool = False
    auto_decision_signals: bool = False
    candidate_availability: CandidateAvailabilityConfirmation | None = None
    candidate_direction_preferences: CandidateDirectionPreferenceConfirmation | None = None
    use_llm: bool = False

    @model_validator(mode="after")
    def validate_candidate_confirmations(self) -> "CareerAgentRequest":
        if self.candidate_availability is not None and not self.auto_decision_signals:
            raise ValueError("candidate_availability requires auto_decision_signals=true")
        if self.candidate_direction_preferences is not None and not self.auto_decision_signals:
            raise ValueError("candidate_direction_preferences requires auto_decision_signals=true")
        return self


@router.post("/runs", response_model=CareerAgentRun)
async def create_agent_run(
    request: CareerAgentRequest,
    repository: Annotated[AgentRunSnapshotRepository, Depends(get_agent_run_repository)],
) -> CareerAgentRun:
    loader = LocalDocumentLoader()
    try:
        resume = loader.load_bytes(request.resume.filename, request.resume.content)
        catalog = loader.load_bytes(request.job_catalog.filename, request.job_catalog.content)
        run = CareerMatchAgent.execute_documents(
            resume,
            catalog,
            top_k=request.top_k,
            include_inactive=request.include_inactive,
            auto_decision_signals=request.auto_decision_signals,
            candidate_availability=request.candidate_availability,
            candidate_direction_preferences=request.candidate_direction_preferences,
            planner=LLMCareerPlanner() if request.use_llm else None,
        )
        snapshot_request = AgentRunRequestSnapshot(
            top_k=request.top_k,
            include_inactive=request.include_inactive,
            auto_decision_signals=request.auto_decision_signals,
            candidate_availability=request.candidate_availability,
            candidate_direction_preferences=request.candidate_direction_preferences,
            use_llm=request.use_llm,
        )
        await repository.save(create_agent_run_snapshot(run, snapshot_request))
        return run
    except (DocumentLoadError, JobCatalogParseError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.get("/runs/{run_id}", response_model=AgentRunSnapshot)
async def get_agent_run(
    run_id: UUID,
    repository: Annotated[AgentRunSnapshotRepository, Depends(get_agent_run_repository)],
) -> AgentRunSnapshot:
    snapshot = await repository.get(run_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found")
    return snapshot


@router.get("/runs", response_model=list[AgentRunSnapshot])
async def list_agent_runs(
    repository: Annotated[AgentRunSnapshotRepository, Depends(get_agent_run_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AgentRunSnapshot]:
    return await repository.list_recent(limit)
