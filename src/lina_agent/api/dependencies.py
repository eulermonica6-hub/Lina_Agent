from typing import cast

from fastapi import Request

from lina_agent.application.conversational_assistant import ConversationalAssistantService
from lina_agent.application.job_discovery import JobDiscoveryService
from lina_agent.application.job_inbox import JobInboxService
from lina_agent.application.repositories import (
    AgentRunSnapshotRepository,
    CandidateConfirmationVersionRepository,
    CandidateProfileRepository,
    DocumentReferenceRepository,
    JobPostingRepository,
)


def get_candidate_repository(request: Request) -> CandidateProfileRepository:
    return cast(CandidateProfileRepository, request.app.state.candidate_repository)


def get_job_repository(request: Request) -> JobPostingRepository:
    return cast(JobPostingRepository, request.app.state.job_repository)


def get_agent_run_repository(request: Request) -> AgentRunSnapshotRepository:
    return cast(AgentRunSnapshotRepository, request.app.state.agent_run_repository)


def get_document_reference_repository(request: Request) -> DocumentReferenceRepository:
    return cast(DocumentReferenceRepository, request.app.state.document_reference_repository)


def get_confirmation_version_repository(
    request: Request,
) -> CandidateConfirmationVersionRepository:
    return cast(
        CandidateConfirmationVersionRepository,
        request.app.state.confirmation_version_repository,
    )


def get_job_search_service(request: Request) -> JobDiscoveryService:
    return cast(JobDiscoveryService, request.app.state.job_search_service)


def get_job_recommendation_service(request: Request) -> JobDiscoveryService:
    return cast(JobDiscoveryService, request.app.state.job_recommendation_service)


def get_job_inbox_service(request: Request) -> JobInboxService:
    return cast(JobInboxService, request.app.state.job_inbox_service)


def get_conversational_assistant(request: Request) -> ConversationalAssistantService:
    return cast(
        ConversationalAssistantService,
        request.app.state.conversational_assistant,
    )
