"""
PDF parsing using Marker (marker-pdf).

High-quality extraction with:
- Math formulas → LaTeX ($$..$$)
- Table structure preservation
- Correct dual-column layout handling
- Section header detection via layout model

Requires: pip install marker-pdf
Optional: --force_ocr for inline math, --use_llm for highest quality

See: https://github.com/datalab-to/marker
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.parsing.pdf_parser import ParsedDocument


# ── Lazy model loading ───────────────────────────────────────────────────
# Marker models are heavy (~3GB). We load them once and reuse.

_converter = None
_converter_config = None


def _get_converter(
    force_ocr: bool = True,
    use_llm: bool = False,
):
    """Get or create a PdfConverter instance (singleton per config)."""
    global _converter, _converter_config

    config_key = (force_ocr, use_llm)
    if _converter is not None and _converter_config == config_key:
        return _converter

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    config = {
        "output_format": "markdown",
        "force_ocr": force_ocr,
        "use_llm": use_llm,
        "disable_tqdm": True,
    }

    config_parser = ConfigParser(config)

    kwargs = {
        "config": config_parser.generate_config_dict(),
        "artifact_dict": create_model_dict(),
        "processor_list": config_parser.get_processors(),
        "renderer": config_parser.get_renderer(),
    }

    # Only add llm_service if use_llm is True
    if use_llm:
        kwargs["llm_service"] = config_parser.get_llm_service()

    _converter = PdfConverter(**kwargs)
    _converter_config = config_key

    return _converter


# ── Public API ───────────────────────────────────────────────────────────

class MarkerParser:
    """
    Parse PDF documents using Marker for high-quality extraction.

    Especially effective for:
    - Academic papers with math formulas
    - Dual-column layouts
    - Tables with complex structure

    Args:
        force_ocr: Force OCR even when text is extractable.
                   Essential for inline math → LaTeX conversion.
                   Default True for academic papers.
        use_llm:   Use LLM for enhanced equation/table quality.
                   Requires API key (Gemini by default).
                   Default False (works great without it for most papers).
    """

    def __init__(
        self,
        force_ocr: bool = True,
        use_llm: bool = False,
    ):
        self.force_ocr = force_ocr
        self.use_llm = use_llm
        self._converter = None

    def _ensure_converter(self):
        """Lazy-load converter on first use."""
        if self._converter is None:
            print("  [marker] Loading models (first call may take 30-60s)...")
            self._converter = _get_converter(
                force_ocr=self.force_ocr,
                use_llm=self.use_llm,
            )
            print("  [marker] Models loaded.")

    def parse(self, path: Path) -> ParsedDocument:
        """
        Parse a PDF file to structured markdown using Marker.

        Args:
            path: Path to PDF file

        Returns:
            ParsedDocument with markdown content (math as LaTeX)
        """
        from marker.output import text_from_rendered

        self._ensure_converter()

        path = Path(path)
        rendered = self._converter(str(path))

        # Extract markdown text and images
        text, _, images = text_from_rendered(rendered)

        # Extract metadata
        metadata = {}
        if hasattr(rendered, "metadata"):
            meta = rendered.metadata
            if hasattr(meta, "model_dump"):
                metadata = meta.model_dump()
            elif isinstance(meta, dict):
                metadata = meta

        # Get page count from metadata
        page_stats = metadata.get("page_stats", [])
        page_count = len(page_stats) if page_stats else 0

        # Get title from table of contents or filename
        title = path.stem
        toc = metadata.get("table_of_contents", [])
        if toc:
            # First h1-level entry is likely the title
            for entry in toc:
                if entry.get("heading_level", 99) <= 1:
                    title = entry.get("title", title)
                    break

        return ParsedDocument(
            document_id=path.stem,
            title=title,
            content=text,
            page_count=page_count,
            metadata={
                "parser": "marker",
                "force_ocr": self.force_ocr,
                "use_llm": self.use_llm,
                "toc": toc,
                "page_stats": page_stats,
            },
        )

    def parse_text(self, text: str, document_id: str = "text") -> ParsedDocument:
        """
        Create ParsedDocument from raw text (for testing).
        Same interface as PDFParser.parse_text().
        """
        return ParsedDocument(
            document_id=document_id,
            title=document_id,
            content=text,
            page_count=1,
            metadata={"parser": "marker", "source": "raw_text"},
        )


# ── Factory function ─────────────────────────────────────────────────────

def is_marker_available() -> bool:
    """Check if marker-pdf is installed."""
    try:
        import marker  # noqa: F401
        return True
    except ImportError:
        return False
