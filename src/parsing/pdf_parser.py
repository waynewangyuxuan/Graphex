"""
PDF parsing using PyMuPDF.

Extracts text with structure preservation (headers, paragraphs).
"""

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class ParsedDocument:
    """Result of parsing a document."""

    document_id: str
    title: str
    content: str  # Markdown formatted
    page_count: int
    metadata: dict = field(default_factory=dict)


class PDFParser:
    """
    Parse PDF documents to structured markdown.

    Uses PyMuPDF for extraction with structure preservation.
    """

    def __init__(self) -> None:
        pass

    def parse(self, path: Path) -> ParsedDocument:
        """
        Parse a PDF file to structured markdown.

        Args:
            path: Path to PDF file

        Returns:
            ParsedDocument with markdown content
        """
        doc = fitz.open(path)

        # Extract metadata
        metadata = doc.metadata or {}
        title = metadata.get("title", path.stem)

        # Extract text from all pages
        content_parts: list[str] = []

        for page_num, page in enumerate(doc, start=1):
            page_text = self._extract_page_text(page, page_num)
            if page_text.strip():
                content_parts.append(page_text)

        content = "\n\n".join(content_parts)

        return ParsedDocument(
            document_id=path.stem,
            title=title,
            content=content,
            page_count=len(doc),
            metadata=metadata,
        )

    def _extract_page_text(self, page: fitz.Page, page_num: int) -> str:
        """
        Extract text from a single page with structure hints.

        Args:
            page: PyMuPDF page object
            page_num: Page number for reference

        Returns:
            Formatted text for the page
        """
        # Get text blocks with position info
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        lines: list[str] = []

        for block in blocks:
            if block["type"] != 0:  # Skip non-text blocks
                continue

            for line in block.get("lines", []):
                text = ""
                for span in line.get("spans", []):
                    text += span.get("text", "")

                text = text.strip()
                if not text:
                    continue

                # Detect headers by font size (heuristic)
                if line.get("spans"):
                    font_size = line["spans"][0].get("size", 12)
                    if font_size > 14:
                        text = f"## {text}"
                    elif font_size > 12:
                        text = f"### {text}"

                lines.append(text)

        return "\n".join(lines)

    def parse_text(self, text: str, document_id: str = "text") -> ParsedDocument:
        """
        Create ParsedDocument from raw text (for testing).

        Args:
            text: Raw text content
            document_id: Identifier for the document

        Returns:
            ParsedDocument
        """
        return ParsedDocument(
            document_id=document_id,
            title=document_id,
            content=text,
            page_count=1,
            metadata={},
        )


# ── Factory ──────────────────────────────────────────────────────────────

def create_parser(backend: str = "auto", **kwargs):
    """
    Create a PDF parser with the specified backend.

    Args:
        backend: "pymupdf" (fast, basic), "marker" (high-quality, slower),
                 or "auto" (marker if available, else pymupdf)
        **kwargs: Passed to the parser constructor.
                  For marker: force_ocr=True, use_llm=False

    Returns:
        Parser instance with .parse(path) and .parse_text(text) methods
    """
    if backend == "auto":
        try:
            from src.parsing.marker_parser import is_marker_available
            if is_marker_available():
                backend = "marker"
            else:
                backend = "pymupdf"
        except ImportError:
            backend = "pymupdf"

    if backend == "marker":
        from src.parsing.marker_parser import MarkerParser
        return MarkerParser(**kwargs)
    elif backend == "pymupdf":
        return PDFParser()
    else:
        raise ValueError(f"Unknown parser backend: {backend!r}. Use 'pymupdf' or 'marker'.")
