"""Narrative Structure extraction pipeline.

Phase 0: Skim → document schema (topic, theme, learning arc)
Phase 1: Sequential chunk extraction → narrative segments + discourse relations

No Phase 2 consolidation — segments don't suffer from entity dedup problems.
Chunking is programmatic (fixed-size + overlap).
"""

import json
import re
import time
from typing import Optional

import litellm

from src.extraction.narrative_prompts import (
    NARRATIVE_SKIM_PROMPT,
    NARRATIVE_CHUNK_TEMPLATE,
)
from src.chunking.programmatic_chunker import chunk_by_sections, Chunk


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
        # For long docs, just pass the opening
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
            # Ensure valid ID
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

        # Track tokens
        total_tokens["input"] += result["tokens"]["input"]
        total_tokens["output"] += result["tokens"]["output"]

        per_chunk_results.append({
            "chunk_id": chunk.chunk_id,
            "new_segments": len(new_segments),
            "new_relations": len(chunk_relations),
            "dropped": len(chunk_dropped),
            "tokens": result["tokens"],
        })

    # Build concept index
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
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def extract_narrative(
    document_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Run the full Narrative Structure extraction pipeline."""

    # Phase 0: Skim
    p0 = phase0_skim(document_text, model=model)
    schema = p0["schema"]

    # Programmatic chunking
    chunks = chunk_by_sections(document_text)

    # Phase 1: Sequential narrative extraction
    p1 = phase1_extract_narrative(document_text, schema, chunks, model=model)

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

    return {
        "segments": p1["segments"],
        "relations": p1["relations"],
        "dropped": p1["dropped"],
        "concept_index": p1["concept_index"],
        "tokens": total_tokens,
        # Intermediate
        "phase0": {"schema": schema},
        "chunking": {
            "method": "programmatic",
            "num_chunks": len(chunks),
            "chunks": chunk_info,
        },
        "phase1": {"per_chunk": p1["per_chunk"]},
    }
