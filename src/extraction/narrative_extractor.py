"""Narrative Structure extraction pipeline.

Phase 0: Skim → document schema (topic, theme, learning arc)
Phase 1: Sequential chunk extraction → narrative segments + discourse relations
Review: LLM-based final cleanup (dedup, relation fixes, concept normalization)
Post-processing: anchor resolution for text-graph binding

Chunking is programmatic (fixed-size + overlap).
"""

import json
import re
from typing import Optional

import litellm

from src.extraction.narrative_prompts import (
    NARRATIVE_SKIM_PROMPT,
    NARRATIVE_CHUNK_TEMPLATE,
    NARRATIVE_REVIEW_PROMPT,
)
from src.chunking.programmatic_chunker import chunk_by_sections, Chunk
from src.binding.anchor_resolver import resolve_anchors, build_segment_ranges
from src.transform.graph_to_tree import graph_to_tree


# ── PDF text pre-processing ──────────────────────────────────────────────

def _preprocess_pdf_text(text: str) -> str:
    """Clean PDF-parsed text to improve LLM extraction reliability.

    Targets:
    - U+FFFD replacement characters (failed PDF glyph conversions)
    - Ligature normalization (ﬁ→fi, ﬂ→fl, ﬀ→ff, etc.)
    - Unicode math symbols → ASCII readable (β→beta, θ→theta, etc.)
    - Excessive whitespace from column layouts
    """
    # 1. Remove U+FFFD replacement characters (PDF parsing artifacts)
    text = text.replace("\ufffd", "")

    # 2. Normalize common ligatures from PDF rendering
    ligatures = {
        "\ufb01": "fi",  # ﬁ
        "\ufb02": "fl",  # ﬂ
        "\ufb00": "ff",  # ﬀ
        "\ufb03": "ffi", # ﬃ
        "\ufb04": "ffl", # ﬄ
    }
    for lig, replacement in ligatures.items():
        text = text.replace(lig, replacement)

    # 3. Normalize Unicode math symbols to ASCII-safe forms.
    #    This prevents LLM from embedding raw Unicode in JSON strings,
    #    which often causes JSON generation to break on math-heavy papers.
    text = _normalize_math_symbols(text)

    # 4. Collapse runs of 3+ spaces (PDF column artifacts) to single space
    text = re.sub(r" {3,}", " ", text)

    # 5. Remove null bytes and other control characters (except \n, \t, \r)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    return text


# Greek letters and math symbols → ASCII readable names
_MATH_SYMBOL_MAP = {
    # Greek lowercase
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
    "ε": "epsilon", "ϵ": "epsilon", "ζ": "zeta", "η": "eta",
    "θ": "theta", "ϑ": "theta", "ι": "iota", "κ": "kappa",
    "λ": "lambda", "μ": "mu", "ν": "nu", "ξ": "xi",
    "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau",
    "υ": "upsilon", "φ": "phi", "ϕ": "phi", "χ": "chi",
    "ψ": "psi", "ω": "omega",
    # Greek uppercase
    "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta", "Λ": "Lambda",
    "Ξ": "Xi", "Π": "Pi", "Σ": "Sigma", "Φ": "Phi",
    "Ψ": "Psi", "Ω": "Omega",
    # Math operators
    "∇": "nabla", "∂": "partial",
    "∞": "inf", "≈": "~=", "≠": "!=",
    "≤": "<=", "≥": ">=", "≪": "<<", "≫": ">>",
    "±": "+/-", "∓": "-/+",
    "×": "x", "÷": "/",
    "·": "*", "∘": "o",
    "√": "sqrt",
    "∈": "in", "∉": "not in",
    "⊂": "subset", "⊃": "superset", "⊆": "subseteq", "⊇": "supseteq",
    "∪": "union", "∩": "intersect",
    "∧": "and", "∨": "or", "¬": "not",
    "∀": "forall", "∃": "exists",
    "∑": "sum", "∏": "prod", "∫": "integral",
    # Arrows
    "→": "->", "←": "<-", "↔": "<->",
    "⇒": "=>", "⇐": "<=", "⇔": "<=>",
    # Special
    "∥": "||", "⊥": "perp",
    "∝": "propto", "∅": "empty",
    "⊗": "otimes", "⊕": "oplus",
    "†": "dagger", "‡": "double-dagger",
    # Common math typography from PDF
    "−": "-",  # U+2212 minus sign → ASCII hyphen
    "′": "'",  # prime
    "″": "\"",  # double prime
    "ℝ": "R", "ℤ": "Z", "ℕ": "N", "ℂ": "C",
}


def _normalize_math_symbols(text: str) -> str:
    """Replace Unicode math symbols with ASCII-readable equivalents.

    This is critical for math-heavy papers (e.g., Adam, BatchNorm) where
    PyMuPDF extracts Unicode Greek letters and operators that cause LLM
    JSON generation to fail. By converting to ASCII, the LLM can safely
    embed these in JSON string values without encoding issues.
    """
    for symbol, replacement in _MATH_SYMBOL_MAP.items():
        text = text.replace(symbol, replacement)

    # Subscript digits: ₀₁₂₃₄₅₆₇₈₉ → _0 _1 ... _9
    subscript_digits = "₀₁₂₃₄₅₆₇₈₉"
    for i, sub in enumerate(subscript_digits):
        text = text.replace(sub, f"_{i}")

    # Superscript digits: ⁰¹²³⁴⁵⁶⁷⁸⁹ → ^0 ^1 ... ^9
    superscript_digits = "⁰¹²³⁴⁵⁶⁷⁸⁹"
    for i, sup in enumerate(superscript_digits):
        text = text.replace(sup, f"^{i}")

    # Subscript letters: ₐ ₑ ₒ ₓ ₔ ₕ ₖ ₗ ₘ ₙ ₚ ₛ ₜ ᵢ ⱼ
    subscript_letters = {
        "ₐ": "_a", "ₑ": "_e", "ₒ": "_o", "ₓ": "_x",
        "ₕ": "_h", "ₖ": "_k", "ₗ": "_l", "ₘ": "_m",
        "ₙ": "_n", "ₚ": "_p", "ₛ": "_s", "ₜ": "_t",
        "ᵢ": "_i", "ⱼ": "_j",
        "₌": "=", "₍": "(", "₎": ")",
    }
    for sub, repl in subscript_letters.items():
        text = text.replace(sub, repl)

    # Superscript letters: ⁿ ⁱ ᵗ ˢ
    superscript_letters = {
        "ⁿ": "^n", "ⁱ": "^i", "ᵗ": "^t", "ˢ": "^s",
        "⁺": "+", "⁻": "-", "⁼": "=",
        "⁽": "(", "⁾": ")",
    }
    for sup, repl in superscript_letters.items():
        text = text.replace(sup, repl)

    # Hat/tilde combining characters (often cause U+FFFD in PDF)
    text = text.replace("\u0302", "^")   # combining circumflex (hat)
    text = text.replace("\u0303", "~")   # combining tilde
    text = text.replace("\u0304", "-")   # combining macron (bar)
    text = text.replace("\u0307", ".")   # combining dot above
    text = text.replace("\u0308", "..")  # combining diaeresis

    return text


# ── JSON parsing ──────────────────────────────────────────────────────────

def _clean_json_text(text: str) -> str:
    """Strip JS-style comments and trailing commas."""
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _parse_json(text: str) -> dict:
    """Parse JSON with fallback extraction."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = _clean_json_text(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        return {}


def _salvage_segments(raw: str) -> list[dict]:
    """Try to extract segments from malformed/truncated JSON output.

    When the LLM produces output that can't be parsed as complete JSON
    (common with math-heavy papers), we try to extract individual segment
    objects from the raw text.
    """
    if not raw:
        return []

    # Strategy 1: Find the segments array and try to parse it in isolation
    seg_match = re.search(r'"segments"\s*:\s*\[', raw)
    if not seg_match:
        return []

    # Extract from segments array start to the end
    array_start = raw.index("[", seg_match.start())
    # Try to find the matching closing bracket
    depth = 0
    end_pos = -1
    for i in range(array_start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    if end_pos > 0:
        array_text = raw[array_start:end_pos]
    else:
        # Array was truncated — try to close it
        # Find last complete object (ending with })
        last_obj_end = raw.rfind("}")
        if last_obj_end > array_start:
            array_text = raw[array_start:last_obj_end + 1] + "]"
        else:
            return []

    # Clean and parse
    array_text = _clean_json_text(array_text)
    try:
        segments = json.loads(array_text)
        if isinstance(segments, list):
            # Validate: each item should have at minimum id and title
            valid = [s for s in segments
                     if isinstance(s, dict) and (s.get("id") or s.get("title"))]
            return valid
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract individual segment objects via regex
    # Match {"id": "s...", ...} patterns
    segments = []
    obj_pattern = re.compile(r'\{[^{}]*"id"\s*:\s*"s\d+"[^{}]*\}')
    for match in obj_pattern.finditer(raw):
        try:
            obj = json.loads(match.group())
            if obj.get("id") and obj.get("title"):
                segments.append(obj)
        except json.JSONDecodeError:
            continue

    return segments


def _call_llm(system: str, user: str, model: str, max_tokens: int = 4096) -> dict:
    """Call LLM and return parsed JSON + token usage."""
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    data = _parse_json(raw)
    tokens = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens,
    }
    return {"data": data, "raw": raw, "tokens": tokens}


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 0: SKIM
# ═══════════════════════════════════════════════════════════════════════════

def phase0_skim(
    document_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    full_doc_token_threshold: int = 20000,
) -> dict:
    """Phase 0: Skim for topic, theme, learning arc."""
    estimated_tokens = len(document_text) // 4

    if estimated_tokens <= full_doc_token_threshold:
        user_content = f"## Full Document\n\n{document_text}"
    else:
        opening_end = int(len(document_text) * 0.15)
        next_break = document_text.find("\n\n", opening_end)
        if 0 < next_break < opening_end * 1.5:
            opening_end = next_break
        user_content = f"## Document Opening\n\n{document_text[:opening_end]}"

    result = _call_llm(NARRATIVE_SKIM_PROMPT, user_content, model, max_tokens=2048)

    return {
        "schema": result["data"],
        "tokens": result["tokens"],
        "raw": result["raw"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: SEQUENTIAL NARRATIVE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def phase1_extract_narrative(
    document_text: str,
    schema: dict,
    chunks: list[Chunk],
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Phase 1: Process chunks sequentially, building narrative graph."""

    topic = schema.get("topic", "")
    theme = schema.get("theme", "")
    learning_arc = schema.get("learning_arc", "")

    # Accumulating state
    all_segments: list[dict] = []
    all_relations: list[dict] = []
    all_dropped: list[dict] = []
    per_chunk_results: list[dict] = []
    total_tokens = {"input": 0, "output": 0}
    next_segment_id = 1

    for chunk in chunks:
        chunk_text = document_text[chunk.start_pos:chunk.end_pos]

        # Build "segments so far" summary for context
        segments_so_far = _build_segments_summary(all_segments)

        # Fill prompt
        prompt = NARRATIVE_CHUNK_TEMPLATE
        prompt = prompt.replace("{topic}", topic)
        prompt = prompt.replace("{theme}", theme)
        prompt = prompt.replace("{learning_arc}", learning_arc)
        prompt = prompt.replace("{segments_so_far}", segments_so_far)
        prompt = prompt.replace("{next_id}", f"s{next_segment_id}")

        # Call LLM
        user_content = f"## Section (chunk {chunk.chunk_id})\n\n{chunk_text}"
        result = _call_llm(prompt, user_content, model, max_tokens=8192)
        data = result["data"]

        # Detect parsing failures: LLM produced output but no segments parsed
        new_segments = data.get("segments", [])
        if not new_segments and result["tokens"]["output"] > 100:
            raw_preview = result["raw"][:500] if result["raw"] else "(empty)"
            print(f"  [extract] WARNING: chunk {chunk.chunk_id} produced 0 segments "
                  f"but used {result['tokens']['output']} output tokens!")
            print(f"  [extract] Raw output preview: {raw_preview}")

            # Attempt salvage: try to extract segments from truncated/malformed JSON
            raw = result["raw"] or ""
            salvaged = _salvage_segments(raw)
            if salvaged:
                print(f"  [extract] Salvaged {len(salvaged)} segments from malformed output")
                new_segments = salvaged
            else:
                # Retry once: the first failure is often due to math-heavy content
                # causing JSON formatting issues in the LLM output
                print(f"  [extract] Retrying chunk {chunk.chunk_id}...")
                retry_result = _call_llm(prompt, user_content, model, max_tokens=8192)
                retry_data = retry_result["data"]
                retry_segs = retry_data.get("segments", [])
                total_tokens["input"] += retry_result["tokens"]["input"]
                total_tokens["output"] += retry_result["tokens"]["output"]
                if retry_segs:
                    print(f"  [extract] Retry succeeded: {len(retry_segs)} segments")
                    new_segments = retry_segs
                    data = retry_data
                    result = retry_result
                else:
                    # Last resort: try salvage on retry output too
                    retry_salvaged = _salvage_segments(retry_result["raw"] or "")
                    if retry_salvaged:
                        print(f"  [extract] Salvaged {len(retry_salvaged)} segments from retry")
                        new_segments = retry_salvaged
                    else:
                        print(f"  [extract] Retry also failed — chunk {chunk.chunk_id} "
                              f"content may be too math-heavy for structured extraction")

        for seg in new_segments:
            if not seg.get("id") or seg["id"] in {s["id"] for s in all_segments}:
                seg["id"] = f"s{next_segment_id}"
                next_segment_id += 1
            else:
                try:
                    num = int(seg["id"].replace("s", ""))
                    next_segment_id = max(next_segment_id, num + 1)
                except ValueError:
                    seg["id"] = f"s{next_segment_id}"
                    next_segment_id += 1

            seg["_source_chunk"] = chunk.chunk_id
            all_segments.append(seg)

        # Collect relations from both top-level AND nested inside segments.
        # Some LLMs embed relations inside each segment object instead of
        # (or in addition to) a top-level "relations" array.
        raw_relations = list(data.get("relations", []))
        for seg in new_segments:
            nested = seg.pop("relations", None)
            if isinstance(nested, list):
                raw_relations.extend(nested)

        # Validate relations
        segment_ids = {s["id"] for s in all_segments}
        chunk_relations = []
        chunk_dropped = []

        for rel in raw_relations:
            issues = []
            if not rel.get("type"):
                issues.append("missing_type")
            if rel.get("source", "") not in segment_ids:
                issues.append(f"unknown_source:{rel.get('source', '')}")
            if rel.get("target", "") not in segment_ids:
                issues.append(f"unknown_target:{rel.get('target', '')}")
            if rel.get("source") == rel.get("target"):
                issues.append("self_loop")

            if issues:
                chunk_dropped.append({"relation": rel, "issues": issues})
            else:
                rel["_source_chunk"] = chunk.chunk_id
                chunk_relations.append(rel)

        all_relations.extend(chunk_relations)
        all_dropped.extend(chunk_dropped)

        total_tokens["input"] += result["tokens"]["input"]
        total_tokens["output"] += result["tokens"]["output"]

        chunk_result = {
            "chunk_id": chunk.chunk_id,
            "new_segments": len(new_segments),
            "new_relations": len(chunk_relations),
            "dropped": len(chunk_dropped),
            "tokens": result["tokens"],
        }
        # Save raw output for chunks that produced 0 segments (diagnostic)
        if not new_segments and result["tokens"]["output"] > 100:
            chunk_result["_raw_output_preview"] = (result["raw"] or "")[:2000]
        per_chunk_results.append(chunk_result)

    concept_index = _build_concept_index(all_segments)

    return {
        "segments": all_segments,
        "relations": all_relations,
        "dropped": all_dropped,
        "concept_index": concept_index,
        "per_chunk": per_chunk_results,
        "tokens": total_tokens,
    }


def _build_segments_summary(segments: list[dict]) -> str:
    """Build a compact summary of existing segments for LLM context."""
    if not segments:
        return "(This is the first section — no prior segments.)"

    lines = []
    for s in segments:
        concepts = ", ".join(c.get("label", "?") for c in s.get("concepts", []))
        lines.append(
            f'- {s["id"]} [{s.get("type", "?")}] "{s.get("title", "?")}" '
            f'(concepts: {concepts or "none"})'
        )
    return "\n".join(lines)


def _build_concept_index(segments: list[dict]) -> dict:
    """Aggregate concept tags across all segments."""
    index: dict[str, list[dict]] = {}
    for seg in segments:
        for concept in seg.get("concepts", []):
            label = concept.get("label", "").strip()
            if not label:
                continue
            if label not in index:
                index[label] = []
            index[label].append({
                "segment_id": seg["id"],
                "role": concept.get("role", "uses"),
            })
    return index


# ═══════════════════════════════════════════════════════════════════════════
# REVIEW PASS: LLM-based final cleanup
# ═══════════════════════════════════════════════════════════════════════════

def review_narrative(
    schema: dict,
    segments: list[dict],
    relations: list[dict],
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """LLM-based review pass: dedup segments, fix relations, normalize concepts."""

    topic = schema.get("topic", "")
    theme = schema.get("theme", "")

    # Build segment list for prompt
    seg_lines = []
    for s in segments:
        concepts = ", ".join(c.get("label", "?") for c in s.get("concepts", []))
        seg_lines.append(
            f'- {s["id"]} [{s.get("type", "?")}] "{s.get("title", "?")}" '
            f'— {s.get("content", "")[:150]}'
            f'\n  concepts: [{concepts}]'
        )
    all_segments_str = "\n".join(seg_lines)

    # Build relation list for prompt
    rel_lines = []
    for r in relations:
        rel_lines.append(
            f'- {r.get("source", "?")} → {r.get("target", "?")} [{r.get("type", "?")}] '
            f'"{r.get("annotation", "")[:80]}"'
        )
    all_relations_str = "\n".join(rel_lines)

    # Collect concept labels
    concept_labels = set()
    for s in segments:
        for c in s.get("concepts", []):
            concept_labels.add(c.get("label", ""))
    concept_labels_str = ", ".join(sorted(concept_labels - {""}))

    # Fill prompt
    prompt = NARRATIVE_REVIEW_PROMPT
    prompt = prompt.replace("{topic}", topic)
    prompt = prompt.replace("{theme}", theme)
    prompt = prompt.replace("{all_segments}", all_segments_str)
    prompt = prompt.replace("{all_relations}", all_relations_str)
    prompt = prompt.replace("{concept_labels}", concept_labels_str)

    result = _call_llm(prompt, "Please review.", model, max_tokens=4096)

    return {
        "data": result["data"],
        "tokens": result["tokens"],
        "raw": result["raw"],
    }


def apply_review(
    segments: list[dict],
    relations: list[dict],
    review_data: dict,
) -> tuple[list[dict], list[dict], dict]:
    """Apply LLM review results to the narrative graph.

    Returns: (updated_segments, updated_relations, applied_log)
    """
    applied_log = {
        "segment_merges": [],
        "relation_fixes": [],
        "concept_merges": [],
    }

    # 1. Apply segment merges
    merge_map: dict[str, str] = {}  # removed_id → kept_id
    remove_ids: set[str] = set()

    for merge in review_data.get("segment_merges", []):
        keep_id = merge.get("keep_id", "")
        remove_id = merge.get("remove_id", "")
        # Validate both IDs exist
        seg_ids = {s["id"] for s in segments}
        if keep_id in seg_ids and remove_id in seg_ids and keep_id != remove_id:
            merge_map[remove_id] = keep_id
            remove_ids.add(remove_id)
            applied_log["segment_merges"].append(merge)

    # Filter segments
    merged_segments = [s for s in segments if s["id"] not in remove_ids]

    # Resolve chain merges: if A→B and B→C, then A→C
    # This prevents dangling references when merges cascade
    def _resolve_chain(merge_map: dict[str, str]) -> dict[str, str]:
        resolved = {}
        for src, tgt in merge_map.items():
            seen = {src}
            cur = tgt
            while cur in merge_map and cur not in seen:
                seen.add(cur)
                cur = merge_map[cur]
            resolved[src] = cur
        return resolved

    merge_map = _resolve_chain(merge_map)

    # Remap relations
    def remap(sid: str) -> str:
        return merge_map.get(sid, sid)

    merged_rels = []
    seen_rel_keys = set()
    for rel in relations:
        new_src = remap(rel.get("source", ""))
        new_tgt = remap(rel.get("target", ""))

        if new_src == new_tgt:
            continue

        key = (new_src, new_tgt, rel.get("type", ""))
        if key in seen_rel_keys:
            continue
        seen_rel_keys.add(key)

        rel_copy = dict(rel)
        rel_copy["source"] = new_src
        rel_copy["target"] = new_tgt
        merged_rels.append(rel_copy)

    # Post-merge validation: drop relations pointing to removed segments
    valid_ids = {s["id"] for s in merged_segments}
    pre_count = len(merged_rels)
    merged_rels = [r for r in merged_rels
                   if r.get("source") in valid_ids and r.get("target") in valid_ids]
    if len(merged_rels) < pre_count:
        applied_log["dangling_dropped"] = pre_count - len(merged_rels)

    # 2. Apply relation type fixes
    for fix in review_data.get("relation_fixes", []):
        if fix.get("action") == "change_type":
            src = fix.get("source", "")
            tgt = fix.get("target", "")
            old_type = fix.get("old_type", "")
            new_type = fix.get("new_type", "")

            for rel in merged_rels:
                if (rel.get("source") == src and rel.get("target") == tgt
                        and rel.get("type") == old_type):
                    rel["type"] = new_type
                    rel["_review_fix"] = True
                    applied_log["relation_fixes"].append(fix)
                    break

    # 3. Apply concept label normalization
    concept_rename_map: dict[str, str] = {}  # old_label → new_label
    for cm in review_data.get("concept_merges", []):
        keep = cm.get("keep_label", "")
        remove = cm.get("remove_label", "")
        if keep and remove and keep != remove:
            concept_rename_map[remove] = keep
            applied_log["concept_merges"].append(cm)

    if concept_rename_map:
        for seg in merged_segments:
            for concept in seg.get("concepts", []):
                old_label = concept.get("label", "")
                if old_label in concept_rename_map:
                    concept["label"] = concept_rename_map[old_label]

    return merged_segments, merged_rels, applied_log


# ═══════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def extract_narrative(
    document_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    skip_review: bool = False,
    skip_tree: bool = False,
) -> dict:
    """Run the full Narrative Structure extraction pipeline."""

    # Pre-process: clean PDF artifacts that cause JSON generation failures
    original_len = len(document_text)
    document_text = _preprocess_pdf_text(document_text)
    cleaned_len = len(document_text)
    if original_len != cleaned_len:
        removed = original_len - cleaned_len
        print(f"  [preprocess] Cleaned {removed} chars of PDF artifacts "
              f"({original_len} → {cleaned_len})")

    # Phase 0: Skim
    p0 = phase0_skim(document_text, model=model)
    schema = p0["schema"]

    # Programmatic chunking
    chunks = chunk_by_sections(document_text)

    # Phase 1: Sequential narrative extraction
    p1 = phase1_extract_narrative(document_text, schema, chunks, model=model)

    segments = p1["segments"]
    relations = p1["relations"]

    # Review pass: LLM-based cleanup
    review_result = None
    review_log = None
    if not skip_review and len(segments) > 0:
        review_result = review_narrative(schema, segments, relations, model=model)
        segments, relations, review_log = apply_review(
            segments, relations, review_result["data"]
        )

    # Anchor resolution: map segments to source text positions
    anchor_matches = resolve_anchors(document_text, segments)
    segment_ranges = build_segment_ranges(document_text, segments, anchor_matches)

    # Attach ranges to segments (with end >= start guard)
    range_map = {r["segment_id"]: r for r in segment_ranges}
    for seg in segments:
        rng = range_map.get(seg["id"])
        if rng and rng["start_char"] >= 0:
            end = rng["end_char"]
            start = rng["start_char"]
            # Guard: end must be >= start
            if end < start:
                end = min(start + 2000, len(document_text))
            seg["source_range"] = {
                "start_char": start,
                "end_char": end,
                "confidence": rng["confidence"],
            }

    # Rebuild concept index after review
    concept_index = _build_concept_index(segments)

    # Build chunk info
    chunk_info = [
        {
            "chunk_id": c.chunk_id,
            "start_pos": c.start_pos,
            "end_pos": c.end_pos,
            "token_estimate": c.token_estimate,
        }
        for c in chunks
    ]

    # Aggregate tokens
    total_tokens = {
        "input": p0["tokens"]["input"] + p1["tokens"]["input"],
        "output": p0["tokens"]["output"] + p1["tokens"]["output"],
        "phase0_input": p0["tokens"]["input"],
        "phase0_output": p0["tokens"]["output"],
        "phase1_input": p1["tokens"]["input"],
        "phase1_output": p1["tokens"]["output"],
    }
    if review_result:
        total_tokens["input"] += review_result["tokens"]["input"]
        total_tokens["output"] += review_result["tokens"]["output"]
        total_tokens["review_input"] = review_result["tokens"]["input"]
        total_tokens["review_output"] = review_result["tokens"]["output"]

    # Anchor resolution stats
    anchor_stats = {
        "total": len(anchor_matches),
        "exact": sum(1 for m in anchor_matches if m.confidence == 1.0),
        "fuzzy": sum(1 for m in anchor_matches if 0 < m.confidence < 1.0),
        "failed": sum(1 for m in anchor_matches if m.confidence == 0.0),
    }

    # Tree structuring: LLM-based graph → tree conversion
    tree_result = None
    if not skip_tree and len(segments) > 0:
        tree_result = graph_to_tree(
            segments=segments,
            relations=relations,
            schema=schema,
            model=model,
        )
        total_tokens["input"] += tree_result["tokens"]["input"]
        total_tokens["output"] += tree_result["tokens"]["output"]
        total_tokens["tree_input"] = tree_result["tokens"]["input"]
        total_tokens["tree_output"] = tree_result["tokens"]["output"]

    return {
        # Graph view (complete)
        "segments": segments,
        "relations": relations,
        "dropped": p1["dropped"],
        "concept_index": concept_index,
        # Tree view (reading)
        "tree": tree_result["tree"] if tree_result else None,
        # Tokens
        "tokens": total_tokens,
        # Review
        "review": review_log,
        "anchors": anchor_stats,
        # Intermediate
        "phase0": {"schema": schema},
        "chunking": {
            "method": "programmatic",
            "num_chunks": len(chunks),
            "chunks": chunk_info,
        },
        "phase1": {"per_chunk": p1["per_chunk"]},
        "tree_decision": tree_result["raw_decision"] if tree_result else None,
    }
