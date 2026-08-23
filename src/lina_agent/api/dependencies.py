from typing import cast

from fastapi import Request

from lina_agent.application.repositories import (
    CandidateProfileRepository,
    JobPostingRepository,
)


def get_candidate_repository(request: Request) -> CandidateProfileRepository:
    return cast(CandidateProfileRepository, request.app.state.candidate_repository)


def get_job_repository(request: Request) -> JobPostingRepository:
    return cast(JobPostingRepository, request.app.state.job_repository)
