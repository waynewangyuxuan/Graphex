"""Convert narrative graph (segments + relations) into a readable tree.

Architecture:
  Extraction (LLM) → Graph → Tree Structuring (LLM) → Tree → Rendering
                       ↓
                 kept as-is for full graph view

The graph is the ground truth — all relations including cross-references
and back-references. The tree is a *reading view* that preserves linearity
and controls depth.

The tree structuring uses an LLM call because:
- Determining spine vs branch requires semantic judgment
- Grouping into acts requires understanding topic transitions
- Parent assignment when multiple incoming edges exist needs context
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import litellm

from src.extraction.narrative_prompts import NARRATIVE_TREE_PROMPT


# ── JSON parsing (shared with narrative_extractor) ───────────────────────

def _clean_json_text(text: str) -> str:
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _parse_json(text: str) -> dict:
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


# ── LLM call ─────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, model: str, max_tokens: int = 4096) -> dict:
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

    # Detect truncated output — LLM hit max_tokens before finishing JSON
    finish = response.choices[0].finish_reason
    if finish == "length" and not data.get("acts"):
        print(f"  [tree] WARNING: output truncated (max_tokens={max_tokens}), "
              f"got {len(raw)} chars, finish_reason=length")

    tokens = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens,
    }
    return {"data": data, "raw": raw, "tokens": tokens}


# ── Core: LLM-based tree structuring ────────────────────────────────────

def graph_to_tree(
    segments: list[dict],
    relations: list[dict],
    schema: Optional[dict] = None,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Convert narrative graph to a reading tree using an LLM.

    Args:
        segments: list of segment dicts from extraction
        relations: list of relation dicts from extraction
        schema: phase0 schema (topic, theme, learning_arc)
        model: LLM model to use

    Returns:
        dict with:
          - "tree": the hierarchical tree structure
          - "tokens": LLM token usage
          - "raw_decision": the LLM's raw structuring decision
    """
    if not segments:
        return {"tree": {"id": "root", "title": "Empty", "children": []}, "tokens": {}}

    seg_map = {s["id"]: s for s in segments}

    # ── Build prompt inputs ──
    seg_lines = []
    for s in segments:
        concepts = ", ".join(c.get("label", "?") for c in s.get("concepts", []))
        imp = s.get("importance", "medium")
        seg_lines.append(
            f'- {s["id"]} [{s.get("type", "?")}] (importance: {imp}) '
            f'"{s.get("title", "?")}" — {s.get("content", "")[:120]}'
            f'\n  concepts: [{concepts}]'
        )
    all_segments_str = "\n".join(seg_lines)

    rel_lines = []
    for r in relations:
        rel_lines.append(
            f'- {r.get("source", "?")} → {r.get("target", "?")} '
            f'[{r.get("type", "?")}] "{r.get("annotation", "")[:60]}"'
        )
    all_relations_str = "\n".join(rel_lines)

    topic = schema.get("topic", "") if schema else ""
    theme = schema.get("theme", "") if schema else ""
    learning_arc = schema.get("learning_arc", "") if schema else ""

    prompt = NARRATIVE_TREE_PROMPT
    prompt = prompt.replace("{topic}", topic)
    prompt = prompt.replace("{theme}", theme)
    prompt = prompt.replace("{learning_arc}", learning_arc)
    prompt = prompt.replace("{all_segments}", all_segments_str)
    prompt = prompt.replace("{all_relations}", all_relations_str)

    # ── Call LLM (scale max_tokens by segment count) ──
    # Each segment needs ~40 tokens in the output (spine_id or branch entry)
    # plus acts overhead. Minimum 4096, scale up for large docs.
    estimated_output = len(segments) * 50 + 500
    max_tokens = max(4096, min(estimated_output, 16384))

    result = _call_llm(prompt, "Please structure this into a reading tree.", model, max_tokens=max_tokens)
    decision = result["data"]

    # If LLM returned empty/truncated, retry once with higher max_tokens
    if not decision.get("acts") and max_tokens < 16384:
        print(f"  [tree] Empty decision, retrying with max_tokens=16384...")
        result = _call_llm(prompt, "Please structure this into a reading tree.", model, max_tokens=16384)
        decision = result["data"]

    # ── Assemble tree from LLM decision ──
    tree = _assemble_tree(segments, decision, schema)

    return {
        "tree": tree,
        "tokens": result["tokens"],
        "raw_decision": decision,
    }


# ── Assembly: combine LLM decision with segment data ────────────────────

def _assemble_tree(
    segments: list[dict],
    decision: dict,
    schema: Optional[dict],
) -> dict:
    """Build the final tree dict from LLM's structuring decision + segment data."""
    seg_map = {s["id"]: s for s in segments}

    # Parse LLM decision
    acts = decision.get("acts", [])
    branches = decision.get("branches", [])
    see_also = decision.get("see_also", [])

    # Collect all spine IDs so we can reject branches that target spine nodes
    spine_ids = set()
    for act in acts:
        for sid in act.get("spine_ids", []):
            spine_ids.add(sid)

    # Build parent→children mapping, filtering out cycles and invalid refs
    children_of: dict[str, list[dict]] = {}  # parent_id → list of {child_id, rel}
    for b in branches:
        pid = b.get("parent_id", "")
        cid = b.get("child_id", "")
        rel = b.get("rel", "")
        if not pid or not cid or pid not in seg_map or cid not in seg_map:
            continue
        if pid == cid:
            continue  # self-loop
        if cid in spine_ids:
            continue  # spine nodes should not be children
        if pid not in children_of:
            children_of[pid] = []
        children_of[pid].append({"child_id": cid, "rel": rel})

    # Detect and break cycles in children_of graph
    def _has_cycle(start: str, visited: set[str]) -> bool:
        if start in visited:
            return True
        visited.add(start)
        for kid in children_of.get(start, []):
            if _has_cycle(kid["child_id"], visited):
                return True
        visited.discard(start)
        return False

    # Remove edges that create cycles
    for pid in list(children_of.keys()):
        safe_kids = []
        for kid in children_of[pid]:
            # Temporarily add and test
            test_visited: set[str] = set()
            children_of[pid] = safe_kids + [kid]
            if _has_cycle(pid, test_visited):
                print(f"  [tree] Broke cycle: {pid} → {kid['child_id']}")
            else:
                safe_kids.append(kid)
        children_of[pid] = safe_kids

    # Build see_also lookup
    see_also_of: dict[str, list[dict]] = {}
    for sa in see_also:
        from_id = sa.get("from", "")
        if from_id:
            if from_id not in see_also_of:
                see_also_of[from_id] = []
            see_also_of[from_id].append(sa)

    # Track which segments are accounted for
    placed = set()
    # Guard against any remaining cycles during recursion
    _building = set()

    def build_node(seg_id: str, rel: str = "") -> Optional[dict]:
        """Recursively build a tree node."""
        seg = seg_map.get(seg_id)
        if not seg:
            return None
        if seg_id in _building:
            return None  # cycle — bail out
        placed.add(seg_id)
        _building.add(seg_id)

        node = {
            "id": seg_id,
            "type": seg.get("type", ""),
            "title": seg.get("title", ""),
            "content": seg.get("content", ""),
            "anchor": seg.get("anchor", ""),
            "concepts": seg.get("concepts", []),
            "importance": seg.get("importance", "medium"),
        }
        if rel:
            node["rel"] = rel
        if seg.get("source_range"):
            node["source_range"] = seg["source_range"]

        # Add see_also
        if seg_id in see_also_of:
            node["see_also"] = see_also_of[seg_id]

        # Recursively add children
        if seg_id in children_of:
            # Sort children by narrative order
            seg_order = {s["id"]: i for i, s in enumerate(segments)}
            kids = sorted(children_of[seg_id],
                          key=lambda c: seg_order.get(c["child_id"], 999))
            node["children"] = []
            for kid in kids:
                child_node = build_node(kid["child_id"], kid["rel"])
                if child_node:
                    node["children"].append(child_node)

        _building.discard(seg_id)
        return node

    # Build acts
    act_nodes = []
    for ai, act in enumerate(acts):
        act_node = {
            "id": f"act{ai + 1}",
            "type": "act",
            "title": act.get("title", f"Act {ai + 1}"),
            "children": [],
        }
        for sid in act.get("spine_ids", []):
            spine_node = build_node(sid)
            if spine_node:
                spine_node["spine"] = True
                act_node["children"].append(spine_node)
        act_nodes.append(act_node)

    # Handle orphans — segments not placed in any act or branch
    orphan_ids = [s["id"] for s in segments if s["id"] not in placed]
    if orphan_ids and act_nodes:
        # Attach to the last act
        for oid in orphan_ids:
            orphan_node = build_node(oid, "related")
            if orphan_node:
                act_nodes[-1]["children"].append(orphan_node)

    # Root
    topic = schema.get("topic", "Narrative") if schema else "Narrative"
    root_title = topic.split(":")[0].strip() if ":" in topic else topic[:60]

    all_spine = sum(
        len(a.get("spine_ids", [])) for a in acts
    )

    root = {
        "id": "root",
        "type": "root",
        "title": root_title,
        "children": act_nodes,
        "meta": {
            "total_segments": len(segments),
            "spine_segments": all_spine,
            "branch_segments": len(segments) - all_spine,
            "acts": len(act_nodes),
            "see_also_count": len(see_also),
        },
    }

    return root
