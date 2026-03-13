#!/usr/bin/env python3
"""Audit anchor resolution quality for a given paper.

Checks if the anchor phrases actually appear near the matched character positions.
Reports accuracy by match type (text-fuzzy, embedding).

Usage:
    python experiments/eval/audit_anchor_quality.py --paper batchnorm
    python experiments/eval/audit_anchor_quality.py --results path/to/output.json --pdf path/to/paper.pdf
"""

import argparse
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditResult:
    """Result of auditing a single segment's anchor."""
    segment_id: str
    anchor_phrase: str
    matched_position: int  # start_char
    confidence: float
    match_type: str  # "exact", "text-fuzzy", "embedding", "failed"
    is_correct: bool
    reason: str  # why it's correct or incorrect
    found_at: Optional[int] = None  # where the anchor phrase was actually found


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from PDF using PyMuPDF."""
    import fitz

    doc = fitz.open(pdf_path)
    text_parts = []

    for page in doc:
        text = page.get_text()
        text_parts.append(text)

    doc.close()
    return "\n".join(text_parts)


def classify_match_type(confidence: float) -> str:
    """Classify match type by confidence level."""
    if confidence == 1.0:
        return "exact"
    elif 0.75 <= confidence < 1.0:
        return "text-fuzzy"
    elif confidence > 0.0:
        return "embedding"
    else:
        return "failed"


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace (including newlines) to single spaces."""
    return re.sub(r'\s+', ' ', text)


def check_anchor_correctness(
    document_text: str,
    segment_id: str,
    anchor_phrase: str,
    matched_start: int,
    confidence: float,
    window_size: int = 200
) -> AuditResult:
    """Check if anchor phrase appears near the matched position."""
    match_type = classify_match_type(confidence)

    if matched_start < 0:
        return AuditResult(
            segment_id=segment_id, anchor_phrase=anchor_phrase,
            matched_position=matched_start, confidence=confidence,
            match_type=match_type, is_correct=False,
            reason="Not resolved (position = -1)")

    if not anchor_phrase.strip():
        return AuditResult(
            segment_id=segment_id, anchor_phrase=anchor_phrase,
            matched_position=matched_start, confidence=confidence,
            match_type=match_type, is_correct=False,
            reason="Empty anchor phrase")

    anchor_lower = anchor_phrase.lower()
    doc_lower = document_text.lower()

    # Strategy 1: Exact case-insensitive match
    exact_pos = doc_lower.find(anchor_lower)
    if exact_pos >= 0:
        distance = abs(exact_pos - matched_start)
        if distance <= window_size:
            return AuditResult(
                segment_id=segment_id, anchor_phrase=anchor_phrase,
                matched_position=matched_start, confidence=confidence,
                match_type=match_type, is_correct=True,
                reason=f"Exact match found {distance} chars away",
                found_at=exact_pos)
        else:
            return AuditResult(
                segment_id=segment_id, anchor_phrase=anchor_phrase,
                matched_position=matched_start, confidence=confidence,
                match_type=match_type, is_correct=False,
                reason=f"Anchor exists but {distance} chars away (expected near {matched_start})",
                found_at=exact_pos)

    # Strategy 2: Normalized whitespace (handles PDF line breaks)
    anchor_norm = normalize_whitespace(anchor_lower)
    doc_norm = normalize_whitespace(doc_lower)
    norm_pos = doc_norm.find(anchor_norm)
    if norm_pos >= 0:
        return AuditResult(
            segment_id=segment_id, anchor_phrase=anchor_phrase,
            matched_position=matched_start, confidence=confidence,
            match_type=match_type, is_correct=True,
            reason="Found after normalizing whitespace",
            found_at=norm_pos)

    # Strategy 3: Prefix matching (first N words)
    words = anchor_phrase.split()
    for n_words in range(min(15, len(words)), max(3, len(words) // 2), -1):
        prefix = " ".join(words[:n_words]).lower()
        prefix_pos = doc_lower.find(prefix)
        if prefix_pos >= 0:
            distance = abs(prefix_pos - matched_start)
            if distance <= window_size:
                return AuditResult(
                    segment_id=segment_id, anchor_phrase=anchor_phrase,
                    matched_position=matched_start, confidence=confidence,
                    match_type=match_type, is_correct=True,
                    reason=f"First {n_words} words found {distance} chars away",
                    found_at=prefix_pos)

    return AuditResult(
        segment_id=segment_id, anchor_phrase=anchor_phrase,
        matched_position=matched_start, confidence=confidence,
        match_type=match_type, is_correct=False,
        reason="Anchor phrase not found in document",
        found_at=None)


def main():
    """Main audit function."""
    parser = argparse.ArgumentParser(description="Audit anchor resolution quality")
    parser.add_argument("--paper", help="Paper ID (looks in experiments/eval/results/ and papers/)")
    parser.add_argument("--results", help="Path to extraction output JSON")
    parser.add_argument("--pdf", help="Path to source PDF")
    args = parser.parse_args()

    # Resolve paths
    eval_dir = Path(__file__).parent
    if args.paper:
        results_path = eval_dir / "results" / f"{args.paper}_output.json"
        pdf_path = eval_dir / "papers" / f"{args.paper}.pdf"
    elif args.results and args.pdf:
        results_path = Path(args.results)
        pdf_path = Path(args.pdf)
    else:
        parser.error("Provide --paper or both --results and --pdf")
        return 1

    if not results_path.exists():
        print(f"ERROR: Results file not found: {results_path}")
        return 1
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return 1

    print("Loading results...")
    with open(results_path) as f:
        data = json.load(f)

    segments = data.get('segments', [])
    print(f"Loaded {len(segments)} segments\n")

    print("Extracting PDF text...")
    document_text = extract_pdf_text(pdf_path)
    print(f"PDF text: {len(document_text)} characters\n")

    # Audit each segment
    audit_results = []
    for seg in segments:
        seg_id = seg.get('id')
        anchor = seg.get('anchor', '').strip()
        sr = seg.get('source_range', {})
        matched_start = sr.get('start_char', -1)
        confidence = sr.get('confidence', 0.0)

        result = check_anchor_correctness(
            document_text, seg_id, anchor, matched_start, confidence)
        audit_results.append(result)

    # Report
    print("\n" + "=" * 80)
    print("ANCHOR RESOLUTION QUALITY AUDIT")
    print("=" * 80 + "\n")

    match_types = {}
    for result in audit_results:
        mt = result.match_type
        if mt not in match_types:
            match_types[mt] = {"total": 0, "correct": 0, "incorrect": 0, "results": []}
        match_types[mt]["total"] += 1
        if result.is_correct:
            match_types[mt]["correct"] += 1
        else:
            match_types[mt]["incorrect"] += 1
        match_types[mt]["results"].append(result)

    for match_type in ["exact", "text-fuzzy", "embedding", "failed"]:
        if match_type not in match_types:
            continue
        stats = match_types[match_type]
        total = stats["total"]
        correct = stats["correct"]
        pct = (correct / total * 100) if total > 0 else 0

        print(f"\n{match_type.upper()}: {total} total")
        print(f"  Correct: {correct} ({pct:.1f}%)")
        print(f"  Incorrect: {stats['incorrect']} ({100 - pct:.1f}%)")

        for result in stats["results"]:
            status = "OK" if result.is_correct else "FAIL"
            anchor_preview = result.anchor_phrase[:70]
            if len(result.anchor_phrase) > 70:
                anchor_preview += "..."
            print(f"    [{status}] {result.segment_id}: {result.reason}")
            print(f"           {anchor_preview}")

    # Summary
    print("\n" + "=" * 80)
    total = len(audit_results)
    correct = sum(1 for r in audit_results if r.is_correct)
    pct = (correct / total * 100) if total > 0 else 0
    print(f"Total: {total}  Correct: {correct} ({pct:.1f}%)  Failed: {total - correct} ({100 - pct:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
