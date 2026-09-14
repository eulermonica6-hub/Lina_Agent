from uuid import uuid4

import pytest
from pydantic import ValidationError

from lina_agent.domain.documents import (
    DocumentBlock,
    DocumentBlockKind,
    DocumentFormat,
    IngestedDocument,
)
from lina_agent.domain.job_catalog import JobCatalogParseError, parse_job_catalog
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


def test_parses_structured_markdown_catalog_with_evidence_and_status() -> None:
    markdown = """# 真实岗位
### 1. Agent 工程师 | 甲公司
标题前说明
**基本信息**
- 地点：上海
**岗位职责**
1. 构建 RAG 应用
**任职要求**
- 熟悉 Python
- LangGraph 经验者优先
**状态与来源**
- 招聘中
- https://example.com/job-1。

### 2. 算法工程师 | 乙公司
**任职要求**
- 掌握 PyTorch
**状态与来源**
- 已下线，不可投递
"""
    document = LocalDocumentLoader().load_bytes("jobs.md", markdown.encode())

    jobs = parse_job_catalog(document)

    assert len(jobs) == 2
    assert jobs[0].catalog_number == 1
    assert jobs[0].title == "Agent 工程师"
    assert jobs[0].company == "甲公司"
    assert jobs[0].basic_info[0].text == "地点：上海"
    assert jobs[0].responsibilities[0].text == "构建 RAG 应用"
    assert jobs[0].requirements[1].text == "LangGraph 经验者优先"
    requirement = jobs[0].requirements[0]
    assert document.text[requirement.start_offset : requirement.end_offset] == "熟悉 Python"
    assert jobs[0].source_url == "https://example.com/job-1"
    assert jobs[0].is_active is True
    assert jobs[1].source_url is None
    assert jobs[1].is_active is False


def test_supports_unknown_status_and_ignores_unsectioned_lines() -> None:
    document = LocalDocumentLoader().load_bytes(
        "jobs.txt",
        "### 3. 数据岗 | 丙公司\n这行不属于任何区段\n**岗位职责**\n-\n数据分析".encode(),
    )

    job = parse_job_catalog(document)[0]

    assert job.is_active is None
    assert job.basic_info == ()
    assert [item.text for item in job.responsibilities] == ["数据分析"]


def test_rejects_document_without_supported_job_headings() -> None:
    document = IngestedDocument(
        id=uuid4(),
        source_name="jobs.md",
        format=DocumentFormat.MARKDOWN,
        content_hash="0" * 64,
        text="只有普通文本",
        blocks=(
            DocumentBlock(
                index=0,
                kind=DocumentBlockKind.PARAGRAPH,
                text="只有普通文本",
                start_offset=0,
                end_offset=6,
            ),
        ),
    )

    with pytest.raises(JobCatalogParseError, match="没有找到"):
        parse_job_catalog(document)


def test_document_block_rejects_non_increasing_offsets() -> None:
    with pytest.raises(ValidationError, match="end_offset must be greater than start_offset"):
        DocumentBlock(
            index=0,
            kind=DocumentBlockKind.PARAGRAPH,
            text="Python",
            start_offset=10,
            end_offset=4,
        )
