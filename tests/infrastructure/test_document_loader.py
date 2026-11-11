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


def make_pdf(*lines: str) -> bytes:
    """Build a tiny, offset-correct single-page PDF with one text block per line."""

    content = "\n".join(
        f"BT /F1 12 Tf 72 {720 - index * 20} Td ({line}) Tj ET" for index, line in enumerate(lines)
    ).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(b"xref\n0 " + str(len(objects) + 1).encode() + b"\n")
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode()
        + b"\n%%EOF\n"
    )
    return bytes(output)


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


@pytest.mark.parametrize("filename", ["resume", "resume.png"])
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


def test_reads_pdf_lines_into_paragraph_blocks() -> None:
    document = LocalDocumentLoader().load_bytes("resume.pdf", make_pdf("Lina Resume", "- Python"))

    assert document.format is DocumentFormat.PDF
    assert [block.text for block in document.blocks] == ["Lina Resume", "- Python"]
    assert all(block.kind is DocumentBlockKind.PARAGRAPH for block in document.blocks)


def test_rejects_invalid_or_textless_pdf() -> None:
    loader = LocalDocumentLoader()

    with pytest.raises(DocumentReadError, match="不是可解析的 PDF"):
        loader.load_bytes("broken.pdf", b"not-a-pdf")
    with pytest.raises(EmptyDocumentError, match="没有可读取的文本"):
        loader.load_bytes("empty.pdf", make_pdf())
