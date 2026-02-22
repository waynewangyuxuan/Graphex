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

        # Process segments
        new_segments = data.get("segments", [])
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

        # Validate relations
        segment_ids = {s["id"] for s in all_segments}
        chunk_relations = []
        chunk_dropped = []

        for rel in data.get("relations", []):
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

        per_chunk_results.append({
            "chunk_id": chunk.chunk_id,
            "new_segments": len(new_segments),
            "new_relations": len(chunk_relations),
            "dropped": len(chunk_dropped),
            "tokens": result["tokens"],
        })

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
