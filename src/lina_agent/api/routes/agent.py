from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Base64Bytes, BaseModel, Field, model_validator

from lina_agent.api.dependencies import (
    get_agent_run_repository,
    get_confirmation_version_repository,
    get_document_reference_repository,
)
from lina_agent.application.agent_run_diff import AgentRunDiff, create_agent_run_diff
from lina_agent.application.agent_run_snapshot import (
    AgentRunRequestSnapshot,
    AgentRunSnapshot,
    create_agent_run_snapshot,
)
from lina_agent.application.career_agent import CareerAgentRun, CareerMatchAgent
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentKind,
    DocumentReference,
    create_confirmation_version,
    create_document_reference,
)
from lina_agent.application.repositories import (
    AgentRunSnapshotRepository,
    CandidateConfirmationVersionRepository,
    DocumentReferenceRepository,
)
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
    run_repository: Annotated[AgentRunSnapshotRepository, Depends(get_agent_run_repository)],
    document_repository: Annotated[
        DocumentReferenceRepository,
        Depends(get_document_reference_repository),
    ],
    confirmation_repository: Annotated[
        CandidateConfirmationVersionRepository,
        Depends(get_confirmation_version_repository),
    ],
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
        resume_reference = create_document_reference(
            resume,
            DocumentKind.CANDIDATE_RESUME,
            len(request.resume.content),
        )
        catalog_reference = create_document_reference(
            catalog,
            DocumentKind.JOB_CATALOG,
            len(request.job_catalog.content),
        )
        confirmation_version = create_confirmation_version(
            request.candidate_availability,
            request.candidate_direction_preferences,
        )
        await document_repository.save(resume_reference)
        await document_repository.save(catalog_reference)
        if confirmation_version is not None:
            await confirmation_repository.save(confirmation_version)
        await run_repository.save(
            create_agent_run_snapshot(
                run,
                snapshot_request,
                candidate_document_reference_id=resume_reference.reference_id,
                job_catalog_document_reference_id=catalog_reference.reference_id,
                candidate_confirmation_version_id=(
                    confirmation_version.version_id if confirmation_version is not None else None
                ),
            )
        )
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


@router.get(
    "/runs/{base_run_id}/diff/{target_run_id}",
    response_model=AgentRunDiff,
)
async def diff_agent_runs(
    base_run_id: UUID,
    target_run_id: UUID,
    run_repository: Annotated[AgentRunSnapshotRepository, Depends(get_agent_run_repository)],
    document_repository: Annotated[
        DocumentReferenceRepository,
        Depends(get_document_reference_repository),
    ],
    confirmation_repository: Annotated[
        CandidateConfirmationVersionRepository,
        Depends(get_confirmation_version_repository),
    ],
) -> AgentRunDiff:
    base = await run_repository.get(base_run_id)
    target = await run_repository.get(target_run_id)
    if base is None or target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found")
    return create_agent_run_diff(
        base,
        target,
        base_candidate_document=await _get_document_reference(
            document_repository,
            base.candidate_document_reference_id,
        ),
        target_candidate_document=await _get_document_reference(
            document_repository,
            target.candidate_document_reference_id,
        ),
        base_job_catalog=await _get_document_reference(
            document_repository,
            base.job_catalog_document_reference_id,
        ),
        target_job_catalog=await _get_document_reference(
            document_repository,
            target.job_catalog_document_reference_id,
        ),
        base_confirmation=await _get_confirmation_version(
            confirmation_repository,
            base.candidate_confirmation_version_id,
        ),
        target_confirmation=await _get_confirmation_version(
            confirmation_repository,
            target.candidate_confirmation_version_id,
        ),
    )


@router.get("/documents/{reference_id}", response_model=DocumentReference)
async def get_document_reference(
    reference_id: UUID,
    repository: Annotated[
        DocumentReferenceRepository,
        Depends(get_document_reference_repository),
    ],
) -> DocumentReference:
    reference = await repository.get(reference_id)
    if reference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return reference


@router.get(
    "/confirmations/{version_id}",
    response_model=CandidateConfirmationVersion,
)
async def get_confirmation_version(
    version_id: UUID,
    repository: Annotated[
        CandidateConfirmationVersionRepository,
        Depends(get_confirmation_version_repository),
    ],
) -> CandidateConfirmationVersion:
    version = await repository.get(version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="confirmation version not found",
        )
    return version


async def _get_document_reference(
    repository: DocumentReferenceRepository,
    reference_id: UUID | None,
) -> DocumentReference | None:
    return await repository.get(reference_id) if reference_id is not None else None


async def _get_confirmation_version(
    repository: CandidateConfirmationVersionRepository,
    version_id: UUID | None,
) -> CandidateConfirmationVersion | None:
    return await repository.get(version_id) if version_id is not None else None
