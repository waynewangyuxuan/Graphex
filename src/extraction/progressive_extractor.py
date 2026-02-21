"""Progressive Understanding pipeline (ADR-0008).

Phase 0: Skim → document schema + narrative root
Phase 1: Sequential chunk extraction with accumulating context
Phase 2: Consolidation (merge, dedup, correct)

Chunking is programmatic (section-based or fixed-size), not AI-driven.
Edge types are open — the model creates descriptive types that make sense.
"""

import json
import re
from typing import Optional

import litellm

from src.extraction.progressive_prompts import (
    SKIM_PROMPT,
    CHUNK_EXTRACT_TEMPLATE,
    CONSOLIDATION_PROMPT_TEMPLATE,
)
from src.chunking.programmatic_chunker import chunk_by_sections, Chunk
from src.validation.phase0_validator import validate_document_schema


# ── JSON parsing (reuse from two_pass_extractor) ─────────────────────────

def _clean_json_text(text: str) -> str:
    """Strip JS-style comments and trailing commas that Gemini sometimes emits."""
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
    opening_ratio: float = 0.15,
    full_doc_token_threshold: int = 20000,
) -> dict:
    """Phase 0: Skim the document to produce document schema + narrative root.

    No longer produces a chunking plan — chunking is programmatic.

    For short documents (< full_doc_token_threshold tokens), passes the full
    text so the model gets complete context.
    For long documents, passes only the opening + section header hints.

    Returns:
        Dict with: schema, schema_issues, tokens, raw.
    """
    estimated_tokens = len(document_text) // 4

    if estimated_tokens <= full_doc_token_threshold:
        user_content = f"""## Full Document (skim for structure, don't extract details)
{document_text}"""
    else:
        opening_end = int(len(document_text) * opening_ratio)
        next_break = document_text.find("\n\n", opening_end)
        if next_break > 0 and next_break < opening_end * 1.5:
            opening_end = next_break
        opening_text = document_text[:opening_end]
        rest_preview = _extract_section_hints(document_text[opening_end:])

        user_content = f"""## Document Opening
{opening_text}

## Rest of Document (section headers/hints only)
{rest_preview}"""

    result = _call_llm(SKIM_PROMPT, user_content, model, max_tokens=4096)
    schema = result["data"]

    # Validate schema structure
    schema_issues = validate_document_schema(schema)

    return {
        "schema": schema,
        "schema_issues": [
            {"severity": i.severity, "message": i.message} for i in schema_issues
        ],
        "tokens": result["tokens"],
        "raw": result["raw"],
    }


def _extract_section_hints(text: str, max_hints: int = 20) -> str:
    """Extract section-header-like lines from text as a lightweight outline."""
    hints = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            hints.append(stripped)
        elif re.match(r'^\d+[\.\d]*\s+\S', stripped):
            hints.append(stripped[:100])
        elif len(stripped) > 5 and stripped == stripped.upper() and stripped[0].isalpha():
            hints.append(stripped[:100])
        elif stripped.startswith("**") and stripped.endswith("**"):
            hints.append(stripped[:100])
        if len(hints) >= max_hints:
            break
    return "\n".join(hints) if hints else "(no clear section headers found)"


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: SEQUENTIAL CHUNK EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def phase1_extract_chunks(
    document_text: str,
    schema: dict,
    chunks: list[Chunk],
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Phase 1: Process chunks sequentially with accumulating context.

    Edge types are open — no validation against a fixed list.
    Only validates: entity IDs exist, no self-loops.
    """
    topic = schema.get("topic", "")
    theme = schema.get("theme", "")
    narrative_root = schema.get("narrative_root", {})
    learning_arc = narrative_root.get("learning_arc", "")

    # Initialize accumulating state
    all_entities: list[dict] = []
    all_relationships: list[dict] = []
    all_dropped: list[dict] = []
    narrative_parts: list[str] = [narrative_root.get("summary", "")]
    per_chunk_results: list[dict] = []
    total_tokens = {"input": 0, "output": 0}
    next_entity_id = 1

    # Seed entity registry with expected core entities from Phase 0
    for expected in schema.get("expected_core_entities", []):
        eid = f"e{next_entity_id}"
        all_entities.append({
            "id": eid,
            "type": expected.get("type", "Concept"),
            "label": expected["label"],
            "definition": f"(predicted from skim — to be refined) {expected.get('why', '')}",
            "importance": "core",
            "_source": "phase0_prediction",
        })
        next_entity_id += 1

    for chunk in chunks:
        chunk_text = document_text[chunk.start_pos:chunk.end_pos]

        # Build narrative so far
        narrative_so_far = " ".join(narrative_parts)
        if len(narrative_so_far) > 2000:
            narrative_so_far = (
                narrative_parts[0]
                + " [...] "
                + " ".join(narrative_parts[-2:])
            )

        # Build entity registry
        entity_lines = []
        for e in all_entities:
            entity_lines.append(
                f'- {e["id"]} [{e["type"]}] "{e["label"]}": {e.get("definition", "")}'
            )
        entity_registry_str = "\n".join(entity_lines) if entity_lines else "(none yet)"

        # Fill prompt template
        prompt = CHUNK_EXTRACT_TEMPLATE
        prompt = prompt.replace("{topic}", topic)
        prompt = prompt.replace("{theme}", theme)
        prompt = prompt.replace("{learning_arc}", learning_arc)
        prompt = prompt.replace("{narrative_so_far}", narrative_so_far)
        prompt = prompt.replace("{entity_registry}", entity_registry_str)
        prompt = prompt.replace("{next_id}", f"e{next_entity_id}")

        # Call LLM
        user_content = f"## Section: {chunk.section} (chunk {chunk.chunk_id})\n\n{chunk_text}"
        result = _call_llm(prompt, user_content, model, max_tokens=8192)
        data = result["data"]

        # Process new entities
        new_entities = data.get("new_entities", [])
        for ent in new_entities:
            if not ent.get("id") or ent["id"] in {e["id"] for e in all_entities}:
                ent["id"] = f"e{next_entity_id}"
                next_entity_id += 1
            else:
                try:
                    num = int(ent["id"].replace("e", ""))
                    next_entity_id = max(next_entity_id, num + 1)
                except ValueError:
                    ent["id"] = f"e{next_entity_id}"
                    next_entity_id += 1
            ent["_source_chunk"] = chunk.chunk_id
            all_entities.append(ent)

        # Validate relationships — open types, only check entity refs + self-loops
        chunk_relationships = []
        chunk_dropped = []
        entity_ids = {e["id"] for e in all_entities}

        for rel in data.get("relationships", []):
            issues = []
            if not rel.get("type"):
                issues.append("missing_type")
            if rel.get("source", "") not in entity_ids:
                issues.append(f"unknown_source:{rel.get('source', '')}")
            if rel.get("target", "") not in entity_ids:
                issues.append(f"unknown_target:{rel.get('target', '')}")
            if rel.get("source") == rel.get("target"):
                issues.append("self_loop")

            if issues:
                chunk_dropped.append({"relationship": rel, "issues": issues})
            else:
                rel["_source_chunk"] = chunk.chunk_id
                chunk_relationships.append(rel)

        all_relationships.extend(chunk_relationships)
        all_dropped.extend(chunk_dropped)

        # Update narrative
        narrative_update = data.get("narrative_update", "")
        if narrative_update:
            narrative_parts.append(narrative_update)

        # Track tokens
        total_tokens["input"] += result["tokens"]["input"]
        total_tokens["output"] += result["tokens"]["output"]

        per_chunk_results.append({
            "chunk_id": chunk.chunk_id,
            "section": chunk.section,
            "new_entities": len(new_entities),
            "new_relationships": len(chunk_relationships),
            "dropped": len(chunk_dropped),
            "narrative_update": narrative_update,
            "tokens": result["tokens"],
        })

    return {
        "entities": all_entities,
        "relationships": all_relationships,
        "dropped": all_dropped,
        "narrative": narrative_parts,
        "per_chunk": per_chunk_results,
        "tokens": total_tokens,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: CONSOLIDATION
# ═══════════════════════════════════════════════════════════════════════════

def phase2_consolidate(
    schema: dict,
    entities: list[dict],
    relationships: list[dict],
    narrative: list[str],
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Phase 2: Review and consolidate the full graph."""
    topic = schema.get("topic", "")
    theme = schema.get("theme", "")

    entity_lines = []
    for e in entities:
        entity_lines.append(
            f'- {e["id"]} [{e.get("type", "?")}] "{e.get("label", "?")}": '
            f'{e.get("definition", "")}'
        )
    all_entities_str = "\n".join(entity_lines)

    rel_lines = []
    for r in relationships:
        rel_lines.append(
            f'- {r.get("source", "?")} → {r.get("target", "?")} [{r.get("type", "?")}] '
            f'"{r.get("evidence", "")[:80]}"'
        )
    all_rels_str = "\n".join(rel_lines)

    full_narrative = "\n\n".join(narrative)

    prompt = CONSOLIDATION_PROMPT_TEMPLATE
    prompt = prompt.replace("{topic}", topic)
    prompt = prompt.replace("{theme}", theme)
    prompt = prompt.replace("{all_entities}", all_entities_str)
    prompt = prompt.replace("{all_relationships}", all_rels_str)
    prompt = prompt.replace("{full_narrative}", full_narrative)

    result = _call_llm(prompt, "Please review and consolidate.", model, max_tokens=8192)
    data = result["data"]

    return {
        "entity_merges": data.get("entity_merges", []),
        "new_relationships": data.get("new_relationships", []),
        "relationship_corrections": data.get("relationship_corrections", []),
        "final_narrative": data.get("final_narrative", ""),
        "tokens": result["tokens"],
        "raw": result["raw"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# APPLY CONSOLIDATION
# ═══════════════════════════════════════════════════════════════════════════

def apply_consolidation(
    entities: list[dict],
    relationships: list[dict],
    consolidation: dict,
) -> tuple[list[dict], list[dict]]:
    """Apply Phase 2 consolidation results to the graph.

    No edge type validation — all types are accepted.
    """
    # Apply entity merges
    merge_map: dict[str, str] = {}
    remove_ids: set[str] = set()
    for merge in consolidation.get("entity_merges", []):
        keep = merge.get("keep_id", "")
        remove = merge.get("remove_id", "")
        if keep and remove:
            merge_map[remove] = keep
            remove_ids.add(remove)

    merged_entities = [e for e in entities if e.get("id") not in remove_ids]

    def remap_id(eid: str) -> str:
        return merge_map.get(eid, eid)

    merged_rels = []
    for rel in relationships:
        rel_copy = dict(rel)
        rel_copy["source"] = remap_id(rel_copy.get("source", ""))
        rel_copy["target"] = remap_id(rel_copy.get("target", ""))
        merged_rels.append(rel_copy)

    # Apply corrections
    correction_keys = set()
    for corr in consolidation.get("relationship_corrections", []):
        key = (corr.get("original_source"), corr.get("original_target"), corr.get("original_type"))
        correction_keys.add(key)
        merged_rels.append({
            "source": remap_id(corr.get("corrected_source", "")),
            "target": remap_id(corr.get("corrected_target", "")),
            "type": corr.get("corrected_type", ""),
            "evidence": corr.get("reason", ""),
            "_source": "consolidation_correction",
        })

    merged_rels = [
        r for r in merged_rels
        if (r.get("source"), r.get("target"), r.get("type")) not in correction_keys
        or r.get("_source") == "consolidation_correction"
    ]

    # Add new relationships — open types, only validate entity refs
    entity_ids = {e["id"] for e in merged_entities}
    for new_rel in consolidation.get("new_relationships", []):
        if (new_rel.get("source", "") in entity_ids
                and new_rel.get("target", "") in entity_ids
                and new_rel.get("type")):
            new_rel["_source"] = "consolidation_new"
            merged_rels.append(new_rel)

    return merged_entities, merged_rels


# ═══════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def extract_progressive(
    document_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    skip_consolidation: bool = False,
) -> dict:
    """Run the full Progressive Understanding pipeline.

    Chunking is programmatic (section-based). Edge types are open.
    """
    # Phase 0: Skim for schema + narrative root
    p0 = phase0_skim(document_text, model=model)
    schema = p0["schema"]

    # Programmatic chunking — no LLM needed
    chunks = chunk_by_sections(document_text)

    # Phase 1: Sequential extraction
    p1 = phase1_extract_chunks(document_text, schema, chunks, model=model)

    # Clean out phase0 predicted entities that were never referenced
    entities = [
        e for e in p1["entities"]
        if e.get("_source") != "phase0_prediction"
        or any(
            r.get("source") == e["id"] or r.get("target") == e["id"]
            for r in p1["relationships"]
        )
    ]

    # Phase 2: Consolidation
    consolidation = None
    final_entities = entities
    final_relationships = p1["relationships"]

    if not skip_consolidation and len(entities) > 0:
        p2 = phase2_consolidate(
            schema, entities, p1["relationships"], p1["narrative"], model=model
        )
        consolidation = p2
        final_entities, final_relationships = apply_consolidation(
            entities, p1["relationships"], p2
        )

    # Aggregate tokens
    total_tokens = {
        "input": p0["tokens"]["input"] + p1["tokens"]["input"],
        "output": p0["tokens"]["output"] + p1["tokens"]["output"],
        "phase0_input": p0["tokens"]["input"],
        "phase0_output": p0["tokens"]["output"],
        "phase1_input": p1["tokens"]["input"],
        "phase1_output": p1["tokens"]["output"],
    }
    if consolidation:
        total_tokens["input"] += consolidation["tokens"]["input"]
        total_tokens["output"] += consolidation["tokens"]["output"]
        total_tokens["phase2_input"] = consolidation["tokens"]["input"]
        total_tokens["phase2_output"] = consolidation["tokens"]["output"]

    # Build chunk info for output
    chunk_info = [
        {
            "chunk_id": c.chunk_id,
            "section": c.section,
            "start_pos": c.start_pos,
            "end_pos": c.end_pos,
            "token_estimate": c.token_estimate,
        }
        for c in chunks
    ]

    return {
        "entities": final_entities,
        "relationships": final_relationships,
        "dropped": p1["dropped"],
        "tokens": total_tokens,
        # Intermediate outputs for inspection
        "phase0": {
            "schema": schema,
        },
        "chunking": {
            "method": "programmatic",
            "num_chunks": len(chunks),
            "chunks": chunk_info,
        },
        "phase1": {
            "per_chunk": p1["per_chunk"],
            "narrative": p1["narrative"],
        },
        "phase2": consolidation,
    }
