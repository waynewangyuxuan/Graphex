# PDF Parsing Upgrade: PyMuPDF → Marker

## Problem

Our current PDF parser (PyMuPDF `fitz.get_text("dict")`) fails on academic papers with math:

- **53 U+FFFD replacement characters** in Adam paper alone (hat notation m̂ₜ → m�)
- Math-heavy chunks cause LLM to produce malformed JSON → **entire chunks lost** (0 segments from chunk 1 of Adam)
- Dual-column layout sometimes merges left/right columns incorrectly
- Table structure lost (cells become scattered text lines)
- Header detection is font-size heuristic only (>14pt → h2, >12pt → h3) — unreliable

## Solution: Marker (`marker-pdf`)

Marker is an open-source PDF → Markdown converter built on transformer-based models (Surya OCR). It's specifically designed for academic/technical documents.

### What Marker Does Better

| Aspect | PyMuPDF (current) | Marker |
|--------|-------------------|--------|
| Math formulas | U+FFFD on complex glyphs | LaTeX: `$$\hat{m}_t$$` |
| Inline math | Completely lost | Detected via OCR → `$\alpha$` |
| Tables | Scattered text lines | Markdown tables with alignment |
| Dual-column | Sometimes merged | Layout model handles correctly |
| Headers | Font-size heuristic | Layout model detection |
| References | No distinction | Tagged as Reference blocks |

### Key Configuration for Academic Papers

```python
MarkerParser(
    force_ocr=True,   # Essential: enables inline math → LaTeX
    use_llm=False,     # Optional: LLM refines equations (needs API key)
)
```

- `force_ocr=True` — Re-OCRs even when text layer exists. **Must be on** for inline math.
- `use_llm=True` — Uses Gemini/Claude to refine equation LaTeX. Better quality but adds cost and latency.
- `redo_inline_math` — Additional pass for inline math (use with `use_llm`).

### Output Format

Marker outputs clean Markdown with:
- Section headers: `# Title`, `## Section`, `### Subsection`
- Display math: `$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$`
- Inline math: `$\beta_1$`, `$\hat{m}_t$`
- Tables: standard Markdown table syntax
- Images: extracted and saved separately (we skip these)
- Footnotes: superscript notation

### Impact on Downstream Pipeline

**Positive effects:**
- `_preprocess_pdf_text()` becomes less critical (but still useful as safety net)
- Chunk quality improves → fewer malformed LLM outputs
- Anchor resolution should improve (cleaner text = better string matching)
- Section headers in markdown → better chunking boundaries

**Things to watch:**
- LaTeX in content may affect LLM extraction prompts (e.g., `$$..$$` blocks mixed with narrative text)
- Token count increases slightly due to LaTeX notation vs raw Unicode
- First-run model download is ~3GB

## Integration

### Files Changed

- `src/parsing/marker_parser.py` — **NEW**: MarkerParser class with lazy model loading
- `src/parsing/pdf_parser.py` — Added `create_parser(backend)` factory function
- `experiments/eval/run_eval.py` — Added `--parser auto|pymupdf|marker` CLI flag

### Usage

```bash
# Install Marker
pip install marker-pdf

# Run eval with Marker
python experiments/eval/run_eval.py --doc adam --parser marker

# Run eval with PyMuPDF (current behavior)
python experiments/eval/run_eval.py --doc adam --parser pymupdf

# Auto-detect (marker if installed, else pymupdf)
python experiments/eval/run_eval.py --doc adam --parser auto
```

### Python API

```python
from src.parsing.pdf_parser import create_parser

# Auto-detect best available
parser = create_parser(backend="auto")
doc = parser.parse(Path("paper.pdf"))
print(doc.content)  # Clean markdown with LaTeX math

# Explicit marker with options
parser = create_parser(backend="marker", force_ocr=True, use_llm=False)
```

## Validation Plan

1. Install marker-pdf on local machine
2. Run Adam paper through both parsers, compare:
   - U+FFFD count (should be 0 with Marker)
   - Math formula representation (should be LaTeX)
   - Segment count from chunk 1 (should be >0 now)
3. Run full Phase 1 with `--parser marker`, compare segment counts and tree quality
4. Check that anchor resolution improves (cleaner text = better matching)

## Future: MinerU as Alternative

If Marker's math quality isn't sufficient, MinerU (by OpenDataLab) is the next option:
- Dedicated UniMERNet model for formula recognition (CDM=0.968 vs Mathpix 0.951)
- Heavier: requires GPU, larger model downloads
- More complex API (Stages-based pipeline)
- Consider for production; Marker is better for MVP iteration speed
