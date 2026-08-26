from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from lina_agent.domain.documents import DocumentBlockKind, DocumentFormat
from lina_agent.infrastructure.document_loader import (
    DocumentReadError,
    EmptyDocumentError,
    LocalDocumentLoader,
    UnsupportedDocumentTypeError,
)

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(body: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{WORD_NAMESPACE}"><w:body>{body}</w:body></w:document>',
        )
    return output.getvalue()


def test_loads_utf8_markdown_into_stable_evidence_blocks() -> None:
    loader = LocalDocumentLoader()
    content = "\ufeff# 标题\r\n- Python\r普通段落".encode()

    document = loader.load_bytes("resume.MD", content)

    assert document.format is DocumentFormat.MARKDOWN
    assert document.text == "# 标题\n- Python\n普通段落"
    assert [block.kind for block in document.blocks] == [
        DocumentBlockKind.HEADING,
        DocumentBlockKind.LIST_ITEM,
        DocumentBlockKind.PARAGRAPH,
    ]
    assert document.blocks[1].start_offset == len("# 标题\n")
    assert document.blocks[1].end_offset == len("# 标题\n- Python")
    assert loader.load_bytes("copy.md", content).id == document.id


def test_loads_text_file_from_path(tmp_path: Path) -> None:
    path = tmp_path / "resume.TXT"
    path.write_text("1. SQL\n", encoding="utf-8")

    document = LocalDocumentLoader().load(path)

    assert document.format is DocumentFormat.TEXT
    assert document.blocks[0].kind is DocumentBlockKind.LIST_ITEM


@pytest.mark.parametrize("filename", ["resume", "resume.pdf"])
def test_rejects_unsupported_document_types(filename: str) -> None:
    with pytest.raises(UnsupportedDocumentTypeError, match="不支持的文档类型"):
        LocalDocumentLoader().load_bytes(filename, b"content")


def test_reports_missing_or_unreadable_files(tmp_path: Path) -> None:
    with pytest.raises(DocumentReadError, match="无法读取文档"):
        LocalDocumentLoader().load(tmp_path / "missing.txt")


def test_rejects_non_utf8_and_empty_text() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(DocumentReadError, match="不是有效的 UTF-8"):
        loader.load_bytes("resume.txt", b"\xff")
    with pytest.raises(EmptyDocumentError, match="没有可读取的文本"):
        loader.load_bytes("resume.txt", b" \r\n\t")


def test_reads_regular_and_textbox_docx_paragraphs_without_duplicates() -> None:
    body = """
    <w:p><w:r><w:t>普通正文</w:t></w:r></w:p>
    <w:p><w:r><w:drawing><w:txbxContent>
      <w:p><w:r><w:t>文本框</w:t><w:t>内容</w:t></w:r></w:p>
    </w:txbxContent></w:drawing></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve"> A\u00a0 B </w:t></w:r></w:p>
    """

    document = LocalDocumentLoader().load_bytes("resume.docx", make_docx(body))

    assert document.format is DocumentFormat.DOCX
    assert [block.text for block in document.blocks] == ["普通正文", "文本框内容", "A B"]
    assert document.text.count("文本框内容") == 1


def test_rejects_invalid_or_textless_docx() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(DocumentReadError, match="不是可解析的 DOCX"):
        loader.load_bytes("broken.docx", b"not-a-zip")
    with pytest.raises(EmptyDocumentError, match="没有可读取的文本"):
        loader.load_bytes("empty.docx", make_docx("<w:p><w:r><w:t/></w:r></w:p>"))
