"""Anchor resolution — maps segment anchor phrases to character positions in the source document.

This enables bidirectional binding between the narrative graph and the source text:
- Graph → Text: click a segment, scroll to the anchored position
- Text → Graph: select text, highlight the corresponding segment(s)

Resolution strategy:
1. Exact substring match → confidence 1.0
2. Case-insensitive match → confidence 0.9
3. Normalized whitespace match → confidence 0.8
4. PDF-cleaned match (dehyphenation) → confidence 0.78
5. Exact match (no ordering) → confidence 0.75
6. Embedding similarity (all remaining) → confidence 0.3–0.7
7. Not found → confidence 0.0
"""

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AnchorMatch:
    """A resolved anchor with its position in the document."""
    segment_id: str
    anchor_phrase: str
    start_char: int
    end_char: int
    confidence: float  # 1.0 = exact, 0.8-0.9 = text fuzzy, 0.3-0.7 = embedding, 0.0 = not found


# ── Sentence splitting ─────────────────────────────────────────────────

def _split_sentences(text: str) -> list[dict]:
    """Split document text into sentence-level units with character positions.

    Returns list of {"start": int, "end": int, "text": str}.
    Uses a regex-based splitter that handles common abbreviations.
    """
    sentences = []
    # Split on sentence-ending punctuation followed by whitespace + uppercase,
    # or on paragraph breaks (double newlines)
    pattern = re.compile(
        r'(?<=[.!?])\s+(?=[A-Z])'   # sentence boundary
        r'|(?<=\n)\n+'               # paragraph boundary
    )

    last_end = 0
    for match in pattern.finditer(text):
        start = last_end
        end = match.start()
        sent_text = text[start:end].strip()
        if sent_text and len(sent_text) > 10:  # skip tiny fragments
            sentences.append({"start": start, "end": end, "text": sent_text})
        last_end = match.end()

    # Last sentence
    if last_end < len(text):
        sent_text = text[last_end:].strip()
        if sent_text and len(sent_text) > 10:
            sentences.append({"start": last_end, "end": len(text), "text": sent_text})

    return sentences


# ── Embedding model (lazy singleton) ───────────────────────────────────

_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformers model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("  [anchor] WARNING: sentence-transformers not installed, "
                  "embedding fallback disabled")
            return None
    return _embedding_model


def _embedding_resolve(
    document_text: str,
    unresolved: list[tuple[int, str, str]],  # (index, seg_id, anchor_phrase)
    sentences: Optional[list[dict]] = None,
    similarity_threshold: float = 0.3,
) -> dict[int, AnchorMatch]:
    """Resolve unresolved anchors using embedding similarity.

    Args:
        document_text: Full document text
        unresolved: List of (result_index, segment_id, anchor_phrase)
        sentences: Pre-split sentences (optional, will be computed if not provided)
        similarity_threshold: Minimum cosine similarity to accept a match

    Returns:
        Dict mapping result_index → AnchorMatch for successfully resolved anchors.
    """
    if not unresolved:
        return {}

    model = _get_embedding_model()
    if model is None:
        return {}

    # Split document into sentences if not provided
    if sentences is None:
        sentences = _split_sentences(document_text)

    if not sentences:
        return {}

    # Encode all sentences and all anchors in batch
    sentence_texts = [s["text"][:512] for s in sentences]  # cap length
    anchor_texts = [item[2] for item in unresolved]

    all_texts = sentence_texts + anchor_texts
    all_embeddings = model.encode(all_texts, normalize_embeddings=True, show_progress_bar=False)

    sent_embeddings = all_embeddings[:len(sentence_texts)]
    anchor_embeddings = all_embeddings[len(sentence_texts):]

    # Cosine similarity matrix: (n_anchors × n_sentences)
    # Normalized embeddings → dot product = cosine similarity
    similarity_matrix = np.dot(anchor_embeddings, sent_embeddings.T)

    resolved = {}
    for i, (result_idx, seg_id, anchor_phrase) in enumerate(unresolved):
        scores = similarity_matrix[i]
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score >= similarity_threshold:
            sent = sentences[best_idx]
            # Map similarity score to confidence: 0.3–0.7 range
            # score 0.3 → conf 0.3, score 0.6 → conf 0.5, score 1.0 → conf 0.7
            confidence = round(min(0.7, 0.3 + best_score * 0.4), 2)
            resolved[result_idx] = AnchorMatch(
                segment_id=seg_id,
                anchor_phrase=anchor_phrase,
                start_char=sent["start"],
                end_char=sent["end"],
                confidence=confidence,
            )

    return resolved


# ── Core resolution ────────────────────────────────────────────────────

def resolve_anchors(
    document_text: str,
    segments: list[dict],
    use_embedding: bool = True,
) -> list[AnchorMatch]:
    """Resolve anchor phrases to character positions in the document.

    Strategy:
    1. Try exact substring match (confidence = 1.0)
    2. Try case-insensitive match (confidence = 0.9)
    3. Try normalized whitespace match (confidence = 0.8)
    4. Collect all remaining → embedding similarity batch (confidence = 0.3–0.7)
    5. Give up (confidence = 0.0)

    Returns list of AnchorMatch, one per segment (in segment order).
    """
    results: list[AnchorMatch] = []
    doc_lower = document_text.lower()
    doc_normalized = _normalize_whitespace(document_text).lower()
    doc_pdf_clean = _normalize_pdf_breaks(document_text)
    doc_pdf_clean_lower = doc_pdf_clean.lower()

    # Track last matched position to enforce ordering (text-based only)
    last_pos = 0

    for seg in segments:
        anchor = seg.get("anchor", "").strip()
        seg_id = seg.get("id", "?")

        if not anchor:
            results.append(AnchorMatch(seg_id, "", -1, -1, 0.0))
            continue

        # --- Text-based exact/near-exact cascade ---

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

        # Try PDF-cleaned match (handles hyphenated line breaks)
        match = _try_pdf_cleaned(document_text, doc_pdf_clean, doc_pdf_clean_lower, anchor, last_pos)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.78))
            last_pos = match[0]
            continue

        # Try exact match without ordering constraint (catches out-of-order anchors)
        match = _try_exact(document_text, anchor, 0)
        if match:
            results.append(AnchorMatch(seg_id, anchor, match[0], match[1], 0.75))
            continue

        # Mark as unresolved — embedding will handle these
        results.append(AnchorMatch(seg_id, anchor, -1, -1, 0.0))

    # ── Embedding pass: resolve all remaining failures ──
    if use_embedding:
        unresolved = []
        for i, m in enumerate(results):
            if m.confidence == 0.0 and m.anchor_phrase:
                unresolved.append((i, m.segment_id, m.anchor_phrase))

        if unresolved:
            n_unresolved = len(unresolved)
            sentences = _split_sentences(document_text)
            resolved = _embedding_resolve(
                document_text, unresolved, sentences=sentences,
            )
            for idx, new_match in resolved.items():
                results[idx] = new_match

            n_resolved = len(resolved)
            n_still_failed = n_unresolved - n_resolved
            print(f"  [anchor] Embedding: resolved {n_resolved}/{n_unresolved}"
                  f" ({n_still_failed} still failed)")

    return results


# ── Text-based matchers ────────────────────────────────────────────────

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


def _normalize_pdf_breaks(text: str) -> str:
    """Normalize PDF-specific artifacts: hyphenated line breaks and stray newlines.

    Handles patterns like 'continu-\\nously' → 'continuously'
    and 'some word\\nother word' → 'some word other word'.
    """
    # Remove hyphenation at line breaks: "continu-\nously" → "continuously"
    text = re.sub(r'-\s*\n\s*', '', text)
    # Collapse remaining newlines to spaces
    text = re.sub(r'\n+', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text


def _try_pdf_cleaned(
    original_text: str,
    pdf_clean: str,
    pdf_clean_lower: str,
    anchor: str,
    start_from: int,
) -> tuple[int, int] | None:
    """Match anchor against PDF-cleaned text (dehyphenated, newlines removed).

    Maps matched position back to the original text using a character index map.
    """
    anchor_clean = _normalize_pdf_breaks(anchor).lower()
    if len(anchor_clean) < 15:
        return None

    # Find in cleaned text
    approx_start = max(0, start_from - 200)
    pos = pdf_clean_lower.find(anchor_clean, approx_start)
    if pos < 0:
        return None

    # Map position back to original text approximately:
    # Search for the first few words of the anchor in the original text near `pos`
    anchor_words = anchor_clean.split()
    first_words = ' '.join(anchor_words[:min(5, len(anchor_words))])
    window_start = max(0, pos - 300)
    window_end = min(len(original_text), pos + len(anchor_clean) + 300)
    window = original_text[window_start:window_end].lower()
    # Also try with newlines removed in the window
    window_clean = re.sub(r'-\s*\n\s*', '', window)
    window_clean = re.sub(r'\n+', ' ', window_clean)

    local_pos = window_clean.find(first_words)
    if local_pos >= 0:
        abs_pos = window_start + local_pos
        return (abs_pos, abs_pos + len(anchor))
    return None


def _try_normalized(text: str, text_norm_lower: str, anchor: str, start_from: int) -> tuple[int, int] | None:
    """Match after normalizing whitespace on both sides.

    Only succeeds if the FULL normalized anchor is found in the normalized text.
    Maps back to original position by searching nearby in the original text.
    """
    anchor_norm = _normalize_whitespace(anchor).lower()
    if len(anchor_norm) < 15:
        return None  # too short for reliable normalized matching

    approx_norm_start = max(0, start_from - 100)
    pos = text_norm_lower.find(anchor_norm, approx_norm_start)
    if pos >= 0:
        # The position in normalized text is approximate in the original.
        # Search a window around it for a long prefix (8+ words) to verify.
        anchor_words = anchor_norm.split()
        min_prefix_words = min(8, len(anchor_words))
        if min_prefix_words < 4:
            return None  # anchor too short for reliable mapping

        window_start = max(0, pos - 300)
        window_end = min(len(text), pos + len(anchor_norm) + 300)
        window = text[window_start:window_end].lower()

        # Try progressively shorter prefixes, but never fewer than 8 words
        for n in range(len(anchor_words), min_prefix_words - 1, -1):
            prefix = ' '.join(anchor_words[:n])
            local_pos = window.find(prefix)
            if local_pos >= 0:
                abs_pos = window_start + local_pos
                return (abs_pos, abs_pos + len(anchor))
    return None


# ── Range building ─────────────────────────────────────────────────────

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
            end = min(match.start_char + 2000, len(document_text))

        ranges.append({
            "segment_id": seg["id"],
            "start_char": match.start_char,
            "end_char": end,
            "confidence": match.confidence,
        })

    return ranges
