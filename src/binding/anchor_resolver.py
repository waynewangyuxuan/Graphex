"""Anchor resolution — maps segment anchor phrases to character positions in the source document.

This enables bidirectional binding between the narrative graph and the source text:
- Graph → Text: click a segment, scroll to the anchored position
- Text → Graph: select text, highlight the corresponding segment(s)
"""

import re
from dataclasses import dataclass


@dataclass
class AnchorMatch:
    """A resolved anchor with its position in the document."""
    segment_id: str
    anchor_phrase: str
    start_char: int
    end_char: int
    confidence: float  # 1.0 = exact match, 0.5-0.9 = fuzzy, 0.0 = not found


def resolve_anchors(
    document_text: str,
    segments: list[dict],
) -> list[AnchorMatch]:
    """Resolve anchor phrases to character positions in the document.

    Strategy:
    1. Try exact substring match (confidence = 1.0)
    2. Try case-insensitive match (confidence = 0.9)
    3. Try normalized whitespace match (confidence = 0.8)
    4. Try first-N-words match (confidence = 0.6)
    5. Give up (confidence = 0.0)

    Returns list of AnchorMatch, one per segment (in segment order).
    """
    results: list[AnchorMatch] = []
    doc_lower = document_text.lower()
    doc_normalized = _normalize_whitespace(document_text).lower()

    # Track last matched position to enforce ordering
    last_pos = 0

    for seg in segments:
        anchor = seg.get("anchor", "").strip()
        seg_id = seg.get("id", "?")

        if not anchor:
            results.append(AnchorMatch(seg_id, "", -1, -1, 0.0))
            continue

        match = _try_exact(document_text, anchor, last_pos)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 1.0))
            last_pos = match[0]
            continue

        match = _try_case_insensitive(document_text, doc_lower, anchor, last_pos)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.9))
            last_pos = match[0]
            continue

        match = _try_normalized(document_text, doc_normalized, anchor, last_pos)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.8))
            last_pos = match[0]
            continue

        match = _try_prefix_words(document_text, doc_lower, anchor, last_pos)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.6))
            last_pos = match[0]
            continue

        # Last resort: try without position constraint
        match = _try_exact(document_text, anchor, 0)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.5))
            continue

        results.append(AnchorMatch(seg_id, anchor, -1, -1, 0.0))

    return results


def _try_exact(text: str, anchor: str, start_from: int) -> tuple[int, int] | None:
    """Exact substring match."""
    pos = text.find(anchor, start_from)
    if pos >= 0:
        return (pos, pos + len(anchor))
    return None


def _try_case_insensitive(text: str, text_lower: str, anchor: str, start_from: int) -> tuple[int, int] | None:
    """Case-insensitive match."""
    anchor_lower = anchor.lower()
    pos = text_lower.find(anchor_lower, start_from)
    if pos >= 0:
        return (pos, pos + len(anchor))
    return None


def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace to single spaces."""
    return re.sub(r'\s+', ' ', text)


def _try_normalized(text: str, text_norm_lower: str, anchor: str, start_from: int) -> tuple[int, int] | None:
    """Match after normalizing whitespace on both sides."""
    anchor_norm = _normalize_whitespace(anchor).lower()
    # We need to find the position in the normalized text, then map back
    # Simpler: search in normalized text from approximate position
    approx_norm_start = max(0, start_from - 100)
    pos = text_norm_lower.find(anchor_norm, approx_norm_start)
    if pos >= 0:
        # Approximate: normalized position ≈ original position
        # Search in a window around this position in the original text
        window_start = max(0, pos - 200)
        window_end = min(len(text), pos + len(anchor_norm) + 200)
        window = text[window_start:window_end].lower()
        # Try to find the anchor words in the window
        anchor_words = anchor_norm.split()
        if len(anchor_words) >= 3:
            # Match first 3 words as a proxy
            prefix = ' '.join(anchor_words[:3])
            local_pos = window.find(prefix)
            if local_pos >= 0:
                abs_pos = window_start + local_pos
                return (abs_pos, abs_pos + len(anchor))
    return None


def _try_prefix_words(text: str, text_lower: str, anchor: str, start_from: int) -> tuple[int, int] | None:
    """Try matching the first N words of the anchor."""
    words = anchor.lower().split()
    # Try progressively shorter prefixes
    for n in range(min(6, len(words)), 2, -1):
        prefix = ' '.join(words[:n])
        pos = text_lower.find(prefix, start_from)
        if pos >= 0:
            return (pos, pos + len(anchor))
    return None


def build_segment_ranges(
    document_text: str,
    segments: list[dict],
    anchor_matches: list[AnchorMatch],
) -> list[dict]:
    """Build approximate text ranges for each segment.

    Uses anchor positions + next anchor position to estimate the text span
    each segment covers.
    """
    ranges = []
    for i, (seg, match) in enumerate(zip(segments, anchor_matches)):
        if match.start_char < 0:
            ranges.append({
                "segment_id": seg["id"],
                "start_char": -1,
                "end_char": -1,
                "confidence": 0.0,
            })
            continue

        # End is the start of the next segment, or end of document
        if i + 1 < len(anchor_matches) and anchor_matches[i + 1].start_char > 0:
            end = anchor_matches[i + 1].start_char
        else:
            # Look for next chunk boundary or use a default span
            end = min(match.start_char + 2000, len(document_text))

        ranges.append({
            "segment_id": seg["id"],
            "start_char": match.start_char,
            "end_char": end,
            "confidence": match.confidence,
        })

    return ranges
