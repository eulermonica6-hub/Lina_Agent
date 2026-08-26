from enum import StrEnum
from uuid import UUID

from pydantic import Field

from lina_agent.domain.models import DomainModel


class DocumentFormat(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    DOCX = "docx"


class DocumentBlockKind(StrEnum):
    HEADING = "heading"
    LIST_ITEM = "list_item"
    PARAGRAPH = "paragraph"


class DocumentBlock(DomainModel):
    index: int = Field(ge=0)
    kind: DocumentBlockKind
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)


class IngestedDocument(DomainModel):
    id: UUID
    source_name: str = Field(min_length=1)
    format: DocumentFormat
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=1)
    blocks: tuple[DocumentBlock, ...] = Field(min_length=1)
