import re

from pydantic import Field

from lina_agent.domain.documents import IngestedDocument
from lina_agent.domain.models import DomainModel, SourceEvidence

_JOB_HEADING = re.compile(
    r"^###\s+(?P<number>\d+)\.\s*(?P<title>[^|\uff5c\n]+?)\s*[|\uff5c]\s*"
    r"(?P<company>[^\n]+?)\s*$",
    re.MULTILINE,
)
_SECTION_HEADERS = {
    "**基本信息**": "basic_info",
    "**岗位职责**": "responsibilities",
    "**任职要求**": "requirements",
    "**状态与来源**": "source_status",
}
_ITEM_PREFIX = re.compile(r"^\s*(?:[-*+](?:\s+|$)|\d+[.、)]\s*)?")
_URL = re.compile(r"https?://[^\s)>\]]+")
_INACTIVE = re.compile(r"已下线|不可投递|已结束|停止招聘|无效")
_ACTIVE = re.compile(r"可投递|招聘中|有效")


class JobCatalogParseError(ValueError):
    """Raised when a document does not contain a supported job catalog structure."""


class CatalogJob(DomainModel):
    catalog_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title_evidence: SourceEvidence
    company_evidence: SourceEvidence
    basic_info: tuple[SourceEvidence, ...] = ()
    responsibilities: tuple[SourceEvidence, ...] = ()
    requirements: tuple[SourceEvidence, ...] = ()
    source_url: str | None = None
    is_active: bool | None = None
    raw_text: str = Field(min_length=1)


def parse_job_catalog(document: IngestedDocument) -> tuple[CatalogJob, ...]:
    headings = tuple(_JOB_HEADING.finditer(document.text))
    if not headings:
        raise JobCatalogParseError("JD 文档中没有找到受支持的岗位标题结构")

    jobs: list[CatalogJob] = []
    for index, heading in enumerate(headings):
        section_end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(document.text)
        )
        raw_text = document.text[heading.start() : section_end].strip()
        section_text = document.text[heading.end() : section_end]
        section_offset = heading.end()
        grouped: dict[str, list[SourceEvidence]] = {
            "basic_info": [],
            "responsibilities": [],
            "requirements": [],
            "source_status": [],
        }
        current_section: str | None = None

        for line_match in re.finditer(r"(?m)^.*$", section_text):
            raw_line = line_match.group()
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue
            if stripped_line in _SECTION_HEADERS:
                current_section = _SECTION_HEADERS[stripped_line]
                continue
            if current_section is None:
                continue

            prefix_end = _ITEM_PREFIX.match(raw_line).end()  # type: ignore[union-attr]
            untrimmed = raw_line[prefix_end:]
            content = untrimmed.strip()
            if not content:
                continue
            leading = len(untrimmed) - len(untrimmed.lstrip())
            start_offset = section_offset + line_match.start() + prefix_end + leading
            grouped[current_section].append(
                SourceEvidence(
                    document_id=document.id,
                    text=content,
                    start_offset=start_offset,
                    end_offset=start_offset + len(content),
                )
            )

        url_match = _URL.search(raw_text)
        title_evidence = _named_evidence(document, heading, "title")
        company_evidence = _named_evidence(document, heading, "company")
        jobs.append(
            CatalogJob(
                catalog_number=int(heading.group("number")),
                title=title_evidence.text,
                company=company_evidence.text,
                title_evidence=title_evidence,
                company_evidence=company_evidence,
                basic_info=tuple(grouped["basic_info"]),
                responsibilities=tuple(grouped["responsibilities"]),
                requirements=tuple(grouped["requirements"]),
                source_url=url_match.group().rstrip("。，；;") if url_match is not None else None,
                is_active=_job_status(raw_text),
                raw_text=raw_text,
            )
        )
    return tuple(jobs)


def _named_evidence(
    document: IngestedDocument,
    match: re.Match[str],
    group_name: str,
) -> SourceEvidence:
    raw_value = match.group(group_name)
    value = raw_value.strip()
    leading = len(raw_value) - len(raw_value.lstrip())
    start_offset = match.start(group_name) + leading
    return SourceEvidence(
        document_id=document.id,
        text=value,
        start_offset=start_offset,
        end_offset=start_offset + len(value),
    )


def _job_status(text: str) -> bool | None:
    if _INACTIVE.search(text) is not None:
        return False
    if _ACTIVE.search(text) is not None:
        return True
    return None
