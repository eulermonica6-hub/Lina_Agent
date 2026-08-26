import re
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from lina_agent.domain.documents import (
    DocumentBlock,
    DocumentBlockKind,
    DocumentFormat,
    IngestedDocument,
)

_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD_PARAGRAPH = f"{{{_WORD_NAMESPACE}}}p"
_WORD_TEXT = f"{{{_WORD_NAMESPACE}}}t"
_LIST_ITEM = re.compile(r"^(?:[-*+]\s+|\d+[.、)]\s*)")
_WHITESPACE = re.compile(r"[\t\u00a0 ]+")


class DocumentLoadError(ValueError):
    """Base error for a local document that cannot be converted into evidence blocks."""


class UnsupportedDocumentTypeError(DocumentLoadError):
    """Raised when no reader is registered for the filename extension."""


class EmptyDocumentError(DocumentLoadError):
    """Raised when a supported document contains no readable text."""


class DocumentReadError(DocumentLoadError):
    """Raised when bytes cannot be decoded as the declared document type."""


class LocalDocumentLoader:
    """Load UTF-8 text, Markdown, and text-bearing DOCX files into one evidence model."""

    def load(self, path: Path) -> IngestedDocument:
        try:
            content = path.read_bytes()
        except OSError as error:
            raise DocumentReadError(f"无法读取文档：{path}") from error
        return self.load_bytes(path.name, content)

    def load_bytes(self, source_name: str, content: bytes) -> IngestedDocument:
        suffix = Path(source_name).suffix.lower()
        if suffix == ".md":
            return self._load_text(source_name, content, DocumentFormat.MARKDOWN)
        if suffix == ".txt":
            return self._load_text(source_name, content, DocumentFormat.TEXT)
        if suffix == ".docx":
            return self._load_docx(source_name, content)
        raise UnsupportedDocumentTypeError(f"不支持的文档类型：{suffix or '无扩展名'}")

    def _load_text(
        self,
        source_name: str,
        content: bytes,
        document_format: DocumentFormat,
    ) -> IngestedDocument:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentReadError(f"{source_name} 不是有效的 UTF-8 文本") from error
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        values = tuple(
            (self._text_block_kind(line.strip()), line.strip())
            for line in normalized.split("\n")
            if line.strip()
        )
        return self._build_document(source_name, content, document_format, values)

    def _load_docx(self, source_name: str, content: bytes) -> IngestedDocument:
        try:
            with ZipFile(BytesIO(content)) as package:
                document_xml = package.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
        except (BadZipFile, KeyError, ElementTree.ParseError) as error:
            raise DocumentReadError(f"{source_name} 不是可解析的 DOCX 文档") from error

        values = tuple(
            (DocumentBlockKind.PARAGRAPH, text)
            for paragraph in root.iter(_WORD_PARAGRAPH)
            if not self._contains_nested_paragraph(paragraph)
            if (text := self._word_paragraph_text(paragraph))
        )
        return self._build_document(source_name, content, DocumentFormat.DOCX, values)

    @staticmethod
    def _contains_nested_paragraph(paragraph: ElementTree.Element) -> bool:
        return any(
            descendant is not paragraph and descendant.tag == _WORD_PARAGRAPH
            for descendant in paragraph.iter()
        )

    @staticmethod
    def _word_paragraph_text(paragraph: ElementTree.Element) -> str:
        text = "".join(node.text for node in paragraph.iter(_WORD_TEXT) if node.text is not None)
        return _WHITESPACE.sub(" ", text).strip()

    @staticmethod
    def _text_block_kind(text: str) -> DocumentBlockKind:
        if text.startswith("#"):
            return DocumentBlockKind.HEADING
        if _LIST_ITEM.match(text) is not None:
            return DocumentBlockKind.LIST_ITEM
        return DocumentBlockKind.PARAGRAPH

    @staticmethod
    def _build_document(
        source_name: str,
        content: bytes,
        document_format: DocumentFormat,
        values: tuple[tuple[DocumentBlockKind, str], ...],
    ) -> IngestedDocument:
        if not values:
            raise EmptyDocumentError(f"{source_name} 中没有可读取的文本")

        blocks: list[DocumentBlock] = []
        offset = 0
        for index, (kind, text) in enumerate(values):
            end_offset = offset + len(text)
            blocks.append(
                DocumentBlock(
                    index=index,
                    kind=kind,
                    text=text,
                    start_offset=offset,
                    end_offset=end_offset,
                )
            )
            offset = end_offset + 1

        digest = sha256(content).hexdigest()
        return IngestedDocument(
            id=uuid5(NAMESPACE_URL, f"lina-document:{digest}"),
            source_name=source_name,
            format=document_format,
            content_hash=digest,
            text="\n".join(block.text for block in blocks),
            blocks=tuple(blocks),
        )
