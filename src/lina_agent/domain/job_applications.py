from datetime import datetime

from pydantic import Field

from lina_agent.domain.models import DomainModel


class JobApplicationRecord(DomainModel):
    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    applied_at: datetime

    @property
    def application_key(self) -> str:
        return f"{self.source_id}:{self.external_id}"
