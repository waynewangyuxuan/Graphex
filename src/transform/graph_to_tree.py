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


# ── Structural constraints ──────────────────────────────────────────────

def _compute_tree_constraints(n_segments: int) -> dict:
    """Compute structural constraints for tree decision based on segment count.

    Returns a dict with numeric bounds and a human-readable summary for prompt injection.
    All ranges are derived from n_segments so the LLM gets concrete targets.
    """
    n = n_segments

    # Spine ratio: 35–55% of total segments
    spine_min = max(3, round(n * 0.35))
    spine_max = max(spine_min + 1, round(n * 0.55))

    # Acts: scale with document size
    if n <= 12:
        acts_min, acts_max = 2, 3
    elif n <= 30:
        acts_min, acts_max = 3, 5
    elif n <= 60:
        acts_min, acts_max = 4, 6
    else:
        acts_min, acts_max = 4, 7

    # Max spine depth: cap at 4 (prevents runaway chains)
    max_spine_depth = 4

    # Top-level spine per act: 2–4
    top_spine_per_act_min = 2
    top_spine_per_act_max = 4

    # Build human-readable summary
    branch_min = n - spine_max
    branch_max = n - spine_min
    summary = (
        f"Total segments: {n}\n"
        f"- Spine count: {spine_min}–{spine_max} segments (target ~{round(n * 0.45)})\n"
        f"- Branch count: {branch_min}–{branch_max} segments\n"
        f"- Acts: {acts_min}–{acts_max}\n"
        f"- Top-level spine per act: {top_spine_per_act_min}–{top_spine_per_act_max}\n"
        f"- Max spine nesting depth: {max_spine_depth} levels (no deeper chains)\n"
        f"- Orphans: 0 (every segment must be placed exactly once)"
    )

    return {
        "spine_min": spine_min,
        "spine_max": spine_max,
        "acts_min": acts_min,
        "acts_max": acts_max,
        "max_spine_depth": max_spine_depth,
        "top_spine_per_act_min": top_spine_per_act_min,
        "top_spine_per_act_max": top_spine_per_act_max,
        "summary": summary,
    }


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

    # ── Compute structural constraints from segment count ──
    n = len(segments)
    constraints = _compute_tree_constraints(n)

    prompt = NARRATIVE_TREE_PROMPT
    prompt = prompt.replace("{topic}", topic)
    prompt = prompt.replace("{theme}", theme)
    prompt = prompt.replace("{learning_arc}", learning_arc)
    prompt = prompt.replace("{all_segments}", all_segments_str)
    prompt = prompt.replace("{all_relations}", all_relations_str)

    # Inject constraint values
    prompt = prompt.replace("{constraints}", constraints["summary"])
    prompt = prompt.replace("{spine_min}", str(constraints["spine_min"]))
    prompt = prompt.replace("{spine_max}", str(constraints["spine_max"]))
    prompt = prompt.replace("{max_spine_depth}", str(constraints["max_spine_depth"]))
    prompt = prompt.replace("{top_spine_per_act_min}", str(constraints["top_spine_per_act_min"]))
    prompt = prompt.replace("{top_spine_per_act_max}", str(constraints["top_spine_per_act_max"]))
    prompt = prompt.replace("{acts_min}", str(constraints["acts_min"]))
    prompt = prompt.replace("{acts_max}", str(constraints["acts_max"]))
    prompt = prompt.replace("{total_segments}", str(n))

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

def _collect_spine_ids(spine_nodes: list) -> set[str]:
    """Recursively collect all spine IDs from nested spine structure."""
    ids = set()
    for node in spine_nodes:
        if isinstance(node, str):
            ids.add(node)
        elif isinstance(node, dict):
            sid = node.get("id", "")
            if sid:
                ids.add(sid)
            for child in node.get("children", []):
                ids.update(_collect_spine_ids([child]))
    return ids


def _flatten_spine_legacy(act: dict) -> list:
    """Handle legacy flat spine_ids format: convert to new nested format."""
    spine_ids = act.get("spine_ids", [])
    if spine_ids:
        # Old format: {"spine_ids": ["s1", "s3", "s5"]}
        return [{"id": sid} for sid in spine_ids]
    return act.get("spine", [])


def _assemble_tree(
    segments: list[dict],
    decision: dict,
    schema: Optional[dict],
) -> dict:
    """Build the final tree dict from LLM's structuring decision + segment data.

    Supports both legacy flat spine_ids and new hierarchical spine format.
    """
    seg_map = {s["id"]: s for s in segments}

    # Parse LLM decision
    acts = decision.get("acts", [])
    branches = decision.get("branches", [])
    see_also = decision.get("see_also", [])

    # Normalize: support both old spine_ids and new spine format
    for act in acts:
        if "spine" not in act:
            act["spine"] = _flatten_spine_legacy(act)

    # Collect ALL spine IDs (including nested sub-spine)
    spine_ids = set()
    for act in acts:
        spine_ids.update(_collect_spine_ids(act["spine"]))

    # Collect spine parent→child relationships from nested spine structure
    spine_children_of: dict[str, list[dict]] = {}

    def _parse_spine_node(node) -> str | None:
        """Parse a spine node (string or dict) and register its children."""
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            sid = node.get("id", "")
            if not sid or sid not in seg_map:
                return None
            children = node.get("children", [])
            if children:
                spine_children_of[sid] = []
                for child in children:
                    child_id = _parse_spine_node(child)
                    if child_id:
                        rel = child.get("rel", "develops") if isinstance(child, dict) else "develops"
                        spine_children_of[sid].append({"child_id": child_id, "rel": rel})
            return sid
        return None

    for act in acts:
        for spine_node in act["spine"]:
            _parse_spine_node(spine_node)

    # Build parent→children mapping for BRANCH nodes
    children_of: dict[str, list[dict]] = {}
    for b in branches:
        pid = b.get("parent_id", "")
        cid = b.get("child_id", "")
        rel = b.get("rel", "")
        if not pid or not cid or pid not in seg_map or cid not in seg_map:
            continue
        if pid == cid:
            continue  # self-loop
        if cid in spine_ids:
            continue  # spine nodes are positioned by spine structure, not branches
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

    for pid in list(children_of.keys()):
        safe_kids = []
        for kid in children_of[pid]:
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
    _building = set()  # cycle guard

    def build_node(seg_id: str, rel: str = "", is_spine: bool = False) -> Optional[dict]:
        """Recursively build a tree node."""
        seg = seg_map.get(seg_id)
        if not seg:
            return None
        if seg_id in _building:
            return None  # cycle guard
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
        if is_spine:
            node["spine"] = True
        if seg.get("source_range"):
            node["source_range"] = seg["source_range"]
        if seg_id in see_also_of:
            node["see_also"] = see_also_of[seg_id]

        # Collect all children: spine sub-children + branch children
        all_kids = []

        # Spine sub-children first (sub-spine nodes)
        for kid in spine_children_of.get(seg_id, []):
            all_kids.append((kid["child_id"], kid["rel"], True))  # is_spine=True

        # Branch children
        for kid in children_of.get(seg_id, []):
            all_kids.append((kid["child_id"], kid["rel"], False))

        if all_kids:
            seg_order = {s["id"]: i for i, s in enumerate(segments)}
            all_kids.sort(key=lambda k: seg_order.get(k[0], 999))
            node["children"] = []
            for kid_id, kid_rel, kid_is_spine in all_kids:
                child_node = build_node(kid_id, kid_rel, is_spine=kid_is_spine)
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
        # Only top-level spine nodes become direct children of the act
        for spine_entry in act["spine"]:
            sid = spine_entry.get("id", "") if isinstance(spine_entry, dict) else spine_entry
            if sid and sid not in placed:
                spine_node = build_node(sid, is_spine=True)
                if spine_node:
                    act_node["children"].append(spine_node)
        act_nodes.append(act_node)

    # Handle orphans — segments not placed in any act or branch
    orphan_ids = [s["id"] for s in segments if s["id"] not in placed]
    if orphan_ids and act_nodes:
        for oid in orphan_ids:
            orphan_node = build_node(oid, "related")
            if orphan_node:
                act_nodes[-1]["children"].append(orphan_node)

    # Root
    topic = schema.get("topic", "Narrative") if schema else "Narrative"
    root_title = topic.split(":")[0].strip() if ":" in topic else topic[:60]

    # Count spine vs branch
    def _count_spine(node_list):
        count = 0
        for n in node_list:
            if n.get("spine"):
                count += 1
            count += _count_spine(n.get("children", []))
        return count

    total_spine = 0
    for act_node in act_nodes:
        total_spine += _count_spine(act_node.get("children", []))

    root = {
        "id": "root",
        "type": "root",
        "title": root_title,
        "children": act_nodes,
        "meta": {
            "total_segments": len(segments),
            "spine_segments": total_spine,
            "branch_segments": len(segments) - total_spine,
            "acts": len(act_nodes),
            "see_also_count": len(see_also),
        },
    }

    return root
