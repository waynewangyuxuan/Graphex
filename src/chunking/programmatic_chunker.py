"""Programmatic document chunking — no LLM needed.

Simple fixed-size chunking with overlap. No header detection, no heuristics.
The narrative from Phase 0 provides semantic context; chunking just needs to
deliver consistently-sized pieces of text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A document chunk with position info."""

    chunk_id: int
    section: str
    start_pos: int
    end_pos: int
    token_estimate: int  # chars // 4


# ── Configuration ──────────────────────────────────────────────────────────

DEFAULT_CHUNK_TOKENS = 2048
DEFAULT_OVERLAP_RATIO = 0.10  # 10% overlap
CHARS_PER_TOKEN = 4


def chunk_by_sections(
    document_text: str,
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> list[Chunk]:
    """Split document into fixed-size chunks with overlap.

    Splits at paragraph boundaries (double newlines) when possible,
    falling back to single newlines, then hard split.

    Args:
        document_text: Full document text.
        chunk_tokens: Target tokens per chunk.
        overlap_ratio: Fraction of chunk to overlap with next (0.10 = 10%).

    Returns:
        List of Chunks with positions into the original text.
    """
    chunk_chars = chunk_tokens * CHARS_PER_TOKEN
    overlap_chars = int(chunk_chars * overlap_ratio)
    doc_len = len(document_text)

    if doc_len == 0:
        return []

    chunks: list[Chunk] = []
    start = 0

    while start < doc_len:
        end = min(start + chunk_chars, doc_len)

        # If not at document end, try to break at a paragraph boundary
        if end < doc_len:
            end = _find_break(document_text, start, end)

        token_est = (end - start) // CHARS_PER_TOKEN

        chunks.append(Chunk(
            chunk_id=len(chunks) + 1,
            section=f"chunk_{len(chunks) + 1}",
            start_pos=start,
            end_pos=end,
            token_estimate=token_est,
        ))

        # Advance: next chunk starts at (end - overlap)
        next_start = end - overlap_chars

        # Guard: must always advance
        if next_start <= start:
            next_start = end

        # If at or past end, we're done
        if next_start >= doc_len:
            break

        # Don't create a tiny trailing chunk
        remaining = doc_len - next_start
        if remaining <= overlap_chars:
            # Extend current chunk to end instead
            chunks[-1].end_pos = doc_len
            chunks[-1].token_estimate = (doc_len - chunks[-1].start_pos) // CHARS_PER_TOKEN
            break

        start = next_start

    return chunks


def _find_break(text: str, start: int, target_end: int) -> int:
    """Find the best break point near target_end.

    Preference: paragraph break (\n\n) > line break (\n) > hard cut.
    Searches backward from target_end within a window.
    """
    window = min(400, (target_end - start) // 4)  # search window

    # Try paragraph break (double newline)
    search_region = text[target_end - window:target_end]
    para_break = search_region.rfind("\n\n")
    if para_break >= 0:
        return target_end - window + para_break + 2  # after the \n\n

    # Try line break
    line_break = search_region.rfind("\n")
    if line_break >= 0:
        return target_end - window + line_break + 1

    # Hard cut at target
    return target_end
