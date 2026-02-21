"""Validate Phase 0 (Skim) output against the actual document text.

Phase 0 produces a document schema including a chunking plan with text markers.
This validator checks that the plan is executable: markers exist, chunks are
reasonable sizes, and they cover the full document without gaps.

Design principle: every LLM output in the Progressive Understanding pipeline
goes through a programmatic validator before being consumed by the next phase.
This is the validator for Phase 0 → Phase 1 handoff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ChunkSlice:
    """A resolved chunk: text markers mapped to actual character positions."""

    chunk_id: int
    section: str
    start_pos: int
    end_pos: int
    text: str
    token_estimate: int  # rough: chars / 4


@dataclass
class ValidationIssue:
    """A single issue found during validation."""

    severity: str  # "error" | "warning"
    chunk_id: int | None
    message: str


@dataclass
class ValidationResult:
    """Result of validating a Phase 0 chunking plan."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    resolved_chunks: list[ChunkSlice] = field(default_factory=list)
    coverage_ratio: float = 0.0  # fraction of document covered by chunks
    gap_ranges: list[tuple[int, int]] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def summary(self) -> str:
        lines = []
        status = "PASS" if self.valid else "FAIL"
        lines.append(f"Chunking Plan Validation: {status}")
        lines.append(f"  Chunks resolved: {len(self.resolved_chunks)}")
        lines.append(f"  Document coverage: {self.coverage_ratio:.1%}")
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for e in self.errors:
                chunk_str = f" (chunk {e.chunk_id})" if e.chunk_id is not None else ""
                lines.append(f"    - {e.message}{chunk_str}")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
            for w in self.warnings:
                chunk_str = f" (chunk {w.chunk_id})" if w.chunk_id is not None else ""
                lines.append(f"    - {w.message}{chunk_str}")
        if self.resolved_chunks:
            lines.append("  Chunk sizes (tokens):")
            for c in self.resolved_chunks:
                lines.append(f"    chunk {c.chunk_id} [{c.section}]: ~{c.token_estimate} tokens")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIN_CHUNK_TOKENS = 100  # chunks smaller than this are suspicious
MAX_CHUNK_TOKENS = 3000  # chunks larger than this may hurt extraction quality
MAX_GAP_CHARS = 200  # gaps larger than this between chunks are flagged
CHARS_PER_TOKEN = 4  # rough estimate for English text


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def _find_marker(text: str, marker: str) -> int | None:
    """Find a marker string in the document text.

    Tries exact match first, then normalized whitespace match,
    then case-insensitive match. Returns character position or None.
    """
    # 1. Exact substring
    pos = text.find(marker)
    if pos >= 0:
        return pos

    # 2. Whitespace-normalized
    normalized_text = re.sub(r"\s+", " ", text)
    normalized_marker = re.sub(r"\s+", " ", marker)
    pos = normalized_text.find(normalized_marker)
    if pos >= 0:
        # Map back to approximate position in original text
        # (good enough for boundary detection)
        return pos

    # 3. Case-insensitive
    pos = normalized_text.lower().find(normalized_marker.lower())
    if pos >= 0:
        return pos

    return None


def validate_chunking_plan(
    document_text: str,
    chunking_plan: list[dict],
    *,
    min_tokens: int = MIN_CHUNK_TOKENS,
    max_tokens: int = MAX_CHUNK_TOKENS,
    max_gap_chars: int = MAX_GAP_CHARS,
) -> ValidationResult:
    """Validate a Phase 0 chunking plan against the actual document.

    Args:
        document_text: The full document text (from PDF parser).
        chunking_plan: List of chunk dicts from Phase 0 output. Each has:
            - chunk_id: int
            - section: str
            - start_marker: str (text phrase marking chunk start)
            - end_marker: str (text phrase marking chunk end)
            - expected_token_range: [min, max] (optional)

    Returns:
        ValidationResult with resolved chunks and any issues.
    """
    issues: list[ValidationIssue] = []
    resolved: list[ChunkSlice] = []
    doc_len = len(document_text)

    if not chunking_plan:
        issues.append(ValidationIssue("error", None, "Chunking plan is empty"))
        return ValidationResult(valid=False, issues=issues)

    # --- Resolve each chunk's markers to positions ---
    for chunk in chunking_plan:
        cid = chunk.get("chunk_id", -1)
        section = chunk.get("section", "unknown")
        start_marker = chunk.get("start_marker", "")
        end_marker = chunk.get("end_marker", "")
        expected_range = chunk.get("expected_token_range")

        # Find start position
        if not start_marker:
            issues.append(ValidationIssue("error", cid, "Missing start_marker"))
            continue

        start_pos = _find_marker(document_text, start_marker)
        if start_pos is None:
            issues.append(ValidationIssue(
                "error", cid,
                f"start_marker not found in document: \"{start_marker[:60]}...\""
            ))
            continue

        # Find end position (search from start_pos onward)
        if not end_marker:
            issues.append(ValidationIssue("error", cid, "Missing end_marker"))
            continue

        end_pos = _find_marker(document_text[start_pos:], end_marker)
        if end_pos is None:
            # Try searching full document (marker might overlap with start)
            end_pos_full = _find_marker(document_text, end_marker)
            if end_pos_full is not None and end_pos_full > start_pos:
                end_pos = end_pos_full
            else:
                issues.append(ValidationIssue(
                    "error", cid,
                    f"end_marker not found after start: \"{end_marker[:60]}...\""
                ))
                continue
        else:
            end_pos = start_pos + end_pos

        # Sanity: end must be after start
        if end_pos <= start_pos:
            issues.append(ValidationIssue(
                "error", cid,
                f"end_pos ({end_pos}) <= start_pos ({start_pos})"
            ))
            continue

        chunk_text = document_text[start_pos:end_pos]
        token_est = len(chunk_text) // CHARS_PER_TOKEN

        resolved.append(ChunkSlice(
            chunk_id=cid,
            section=section,
            start_pos=start_pos,
            end_pos=end_pos,
            text=chunk_text,
            token_estimate=token_est,
        ))

        # --- Size checks ---
        if token_est < min_tokens:
            issues.append(ValidationIssue(
                "warning", cid,
                f"Chunk too small: ~{token_est} tokens (min: {min_tokens})"
            ))

        if token_est > max_tokens:
            issues.append(ValidationIssue(
                "warning", cid,
                f"Chunk too large: ~{token_est} tokens (max: {max_tokens})"
            ))

        # Check against LLM's own expected range
        if expected_range and len(expected_range) == 2:
            exp_min, exp_max = expected_range
            if token_est < exp_min * 0.5:
                issues.append(ValidationIssue(
                    "warning", cid,
                    f"Chunk much smaller than LLM expected: ~{token_est} vs [{exp_min}, {exp_max}]"
                ))
            elif token_est > exp_max * 2:
                issues.append(ValidationIssue(
                    "warning", cid,
                    f"Chunk much larger than LLM expected: ~{token_est} vs [{exp_min}, {exp_max}]"
                ))

    # --- Ordering check ---
    if len(resolved) >= 2:
        for i in range(len(resolved) - 1):
            if resolved[i].start_pos >= resolved[i + 1].start_pos:
                issues.append(ValidationIssue(
                    "error", resolved[i + 1].chunk_id,
                    f"Chunk order violation: chunk {resolved[i].chunk_id} starts at "
                    f"{resolved[i].start_pos}, chunk {resolved[i+1].chunk_id} starts at "
                    f"{resolved[i+1].start_pos}"
                ))

    # --- Gap detection ---
    gaps: list[tuple[int, int]] = []
    if resolved:
        # Sort by start position for gap analysis
        sorted_chunks = sorted(resolved, key=lambda c: c.start_pos)

        # Gap before first chunk
        if sorted_chunks[0].start_pos > max_gap_chars:
            gap_size = sorted_chunks[0].start_pos
            gaps.append((0, gap_size))
            issues.append(ValidationIssue(
                "warning", sorted_chunks[0].chunk_id,
                f"Large gap before first chunk: {gap_size} chars uncovered"
            ))

        # Gaps between chunks
        for i in range(len(sorted_chunks) - 1):
            gap_start = sorted_chunks[i].end_pos
            gap_end = sorted_chunks[i + 1].start_pos
            if gap_end > gap_start + max_gap_chars:
                gap_size = gap_end - gap_start
                gaps.append((gap_start, gap_end))
                issues.append(ValidationIssue(
                    "warning", sorted_chunks[i + 1].chunk_id,
                    f"Gap of {gap_size} chars between chunk {sorted_chunks[i].chunk_id} "
                    f"and chunk {sorted_chunks[i+1].chunk_id}"
                ))

        # Gap after last chunk
        tail = doc_len - sorted_chunks[-1].end_pos
        if tail > max_gap_chars:
            gaps.append((sorted_chunks[-1].end_pos, doc_len))
            issues.append(ValidationIssue(
                "warning", None,
                f"Large gap after last chunk: {tail} chars uncovered at document end"
            ))

    # --- Coverage ---
    covered_chars = sum(c.end_pos - c.start_pos for c in resolved)
    coverage = covered_chars / doc_len if doc_len > 0 else 0.0

    if coverage < 0.8:
        issues.append(ValidationIssue(
            "error", None,
            f"Low document coverage: {coverage:.1%} (expected >= 80%)"
        ))
    elif coverage < 0.9:
        issues.append(ValidationIssue(
            "warning", None,
            f"Moderate document coverage: {coverage:.1%} (ideal >= 90%)"
        ))

    # --- Overlap detection ---
    if len(resolved) >= 2:
        sorted_chunks = sorted(resolved, key=lambda c: c.start_pos)
        for i in range(len(sorted_chunks) - 1):
            if sorted_chunks[i].end_pos > sorted_chunks[i + 1].start_pos:
                overlap = sorted_chunks[i].end_pos - sorted_chunks[i + 1].start_pos
                # Small overlaps at boundaries are ok (marker text itself)
                if overlap > 200:
                    issues.append(ValidationIssue(
                        "warning",
                        sorted_chunks[i + 1].chunk_id,
                        f"Significant overlap ({overlap} chars) between "
                        f"chunk {sorted_chunks[i].chunk_id} and chunk {sorted_chunks[i+1].chunk_id}"
                    ))

    has_errors = any(i.severity == "error" for i in issues)

    return ValidationResult(
        valid=not has_errors,
        issues=issues,
        resolved_chunks=resolved,
        coverage_ratio=coverage,
        gap_ranges=gaps,
    )


def validate_document_schema(schema: dict) -> list[ValidationIssue]:
    """Validate the structural completeness of a Phase 0 schema.

    Checks that all required fields are present and non-empty,
    independent of the actual document text.
    """
    issues: list[ValidationIssue] = []

    # Required top-level fields (chunking_plan no longer required — chunking is programmatic)
    required = ["topic", "content_type", "theme", "narrative_root",
                "expected_core_entities", "document_structure"]
    for key in required:
        if key not in schema or not schema[key]:
            issues.append(ValidationIssue("error", None, f"Missing required field: {key}"))

    # Content type should be a known value
    KNOWN_CONTENT_TYPES = {
        "research_paper", "textbook_chapter", "lecture_notes",
        "technical_documentation", "tutorial", "survey_paper",
        "blog_post", "other",
    }
    ct = schema.get("content_type", "")
    if ct and ct not in KNOWN_CONTENT_TYPES:
        issues.append(ValidationIssue(
            "warning", None,
            f"Unknown content_type '{ct}'. Known types: {sorted(KNOWN_CONTENT_TYPES)}"
        ))

    # Narrative root structure
    nr = schema.get("narrative_root", {})
    if isinstance(nr, dict):
        for subkey in ["summary", "key_tension", "learning_arc"]:
            if subkey not in nr or not nr[subkey]:
                issues.append(ValidationIssue(
                    "warning", None,
                    f"narrative_root missing '{subkey}'"
                ))

    # Expected core entities should have label and type
    for i, entity in enumerate(schema.get("expected_core_entities", [])):
        if not entity.get("label"):
            issues.append(ValidationIssue(
                "warning", None, f"expected_core_entities[{i}] missing label"
            ))
        if not entity.get("type"):
            issues.append(ValidationIssue(
                "warning", None, f"expected_core_entities[{i}] missing type"
            ))

    # Chunking plan entries need markers
    for chunk in schema.get("chunking_plan", []):
        cid = chunk.get("chunk_id", "?")
        if not chunk.get("start_marker"):
            issues.append(ValidationIssue(
                "error", cid, f"Chunk {cid} missing start_marker"
            ))
        if not chunk.get("end_marker"):
            issues.append(ValidationIssue(
                "error", cid, f"Chunk {cid} missing end_marker"
            ))

    return issues
