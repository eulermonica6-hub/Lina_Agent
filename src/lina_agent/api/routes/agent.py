from fastapi import APIRouter, HTTPException, status
from pydantic import Base64Bytes, BaseModel, Field, model_validator

from lina_agent.application.career_agent import CareerAgentRun, CareerMatchAgent
from lina_agent.domain.career_matching import CandidateAvailabilityConfirmation
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
    use_llm: bool = False

    @model_validator(mode="after")
    def validate_candidate_availability(self) -> "CareerAgentRequest":
        if self.candidate_availability is not None and not self.auto_decision_signals:
            raise ValueError("candidate_availability requires auto_decision_signals=true")
        return self


@router.post("/runs", response_model=CareerAgentRun)
def create_agent_run(request: CareerAgentRequest) -> CareerAgentRun:
    loader = LocalDocumentLoader()
    try:
        resume = loader.load_bytes(request.resume.filename, request.resume.content)
        catalog = loader.load_bytes(request.job_catalog.filename, request.job_catalog.content)
        return CareerMatchAgent.execute_documents(
            resume,
            catalog,
            top_k=request.top_k,
            include_inactive=request.include_inactive,
            auto_decision_signals=request.auto_decision_signals,
            candidate_availability=request.candidate_availability,
            planner=LLMCareerPlanner() if request.use_llm else None,
        )
    except (DocumentLoadError, JobCatalogParseError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
