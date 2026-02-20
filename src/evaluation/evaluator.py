"""Evaluate extracted knowledge graphs against ground truth.

Uses fuzzy label matching for nodes and (source_label, target_label, type) for edges.
"""

import json
from pathlib import Path


def evaluate_against_ground_truth(
    extracted: dict,
    ground_truth_path: Path,
) -> dict:
    """
    Compare extracted results against ground truth.

    Args:
        extracted: Dict with keys: entities, relationships, tokens.
        ground_truth_path: Path to ground_truth.json.

    Returns:
        Evaluation dict with nodes/edges recall metrics and token usage.
    """
    with open(ground_truth_path) as f:
        gt = json.load(f)

    gt_nodes = gt.get("nodes", {})
    gt_edges = gt.get("edges", {})

    # ---- Node matching ----
    gt_node_labels: dict[str, dict] = {}
    gt_core_labels: set[str] = set()
    for nid, node in gt_nodes.items():
        if nid.startswith("_"):
            continue
        label = node.get("label", "").lower().strip()
        gt_node_labels[label] = node
        if node.get("importance") == "core":
            gt_core_labels.add(label)

    extracted_labels: set[str] = set()
    for entity in extracted["entities"]:
        extracted_labels.add(entity.get("label", "").lower().strip())

    # Fuzzy matching: substring containment in either direction
    matched_all: set[str] = set()
    matched_core: set[str] = set()
    for ext_label in extracted_labels:
        for gt_label in gt_node_labels:
            if ext_label == gt_label or ext_label in gt_label or gt_label in ext_label:
                matched_all.add(gt_label)
                if gt_label in gt_core_labels:
                    matched_core.add(gt_label)

    total_gt_nodes = len([k for k in gt_nodes if not k.startswith("_")])
    total_gt_core = len(gt_core_labels)

    # ---- Edge matching ----
    gt_edge_set: set[tuple[str, str, str]] = set()
    gt_core_edge_set: set[tuple[str, str, str]] = set()
    for eid, edge in gt_edges.items():
        if eid.startswith("_"):
            continue
        src_node = gt_nodes.get(edge.get("source_id", ""), {})
        tgt_node = gt_nodes.get(edge.get("target_id", ""), {})
        src_label = src_node.get("label", "").lower().strip()
        tgt_label = tgt_node.get("label", "").lower().strip()
        edge_type = edge.get("type", "")
        gt_edge_set.add((src_label, tgt_label, edge_type))
        if edge.get("importance") == "core":
            gt_core_edge_set.add((src_label, tgt_label, edge_type))

    entity_id_to_label: dict[str, str] = {}
    for entity in extracted["entities"]:
        entity_id_to_label[entity.get("id", "")] = (
            entity.get("label", "").lower().strip()
        )

    extracted_edge_set: set[tuple[str, str, str]] = set()
    for rel in extracted["relationships"]:
        src_label = entity_id_to_label.get(
            rel.get("source", ""), rel.get("source", "").lower()
        )
        tgt_label = entity_id_to_label.get(
            rel.get("target", ""), rel.get("target", "").lower()
        )
        edge_type = rel.get("type", "")
        extracted_edge_set.add((src_label, tgt_label, edge_type))

    # Match edges (fuzzy on labels, exact on type)
    matched_edges: set[tuple[str, str, str]] = set()
    matched_core_edges: set[tuple[str, str, str]] = set()
    for ext_edge in extracted_edge_set:
        ext_src, ext_tgt, ext_type = ext_edge
        for gt_edge in gt_edge_set:
            gt_src, gt_tgt, gt_type = gt_edge
            src_match = (
                ext_src == gt_src or ext_src in gt_src or gt_src in ext_src
            )
            tgt_match = (
                ext_tgt == gt_tgt or ext_tgt in gt_tgt or gt_tgt in ext_tgt
            )
            type_match = ext_type == gt_type
            if src_match and tgt_match and type_match:
                matched_edges.add(gt_edge)
                if gt_edge in gt_core_edge_set:
                    matched_core_edges.add(gt_edge)

    total_gt_edges = len([k for k in gt_edges if not k.startswith("_")])
    total_gt_core_edges = len(gt_core_edge_set)

    # ---- Edge type distribution ----
    type_dist: dict[str, int] = {}
    for rel in extracted["relationships"]:
        t = rel.get("type", "Unknown")
        type_dist[t] = type_dist.get(t, 0) + 1

    return {
        "nodes": {
            "total_extracted": len(extracted["entities"]),
            "total_gt": total_gt_nodes,
            "matched_all": len(matched_all),
            "matched_core": len(matched_core),
            "total_gt_core": total_gt_core,
            "recall_all": len(matched_all) / total_gt_nodes if total_gt_nodes else 0,
            "recall_core": len(matched_core) / total_gt_core if total_gt_core else 0,
            "matched_labels": sorted(matched_all),
            "missed_core": sorted(gt_core_labels - matched_core),
        },
        "edges": {
            "total_extracted": len(extracted["relationships"]),
            "total_gt": total_gt_edges,
            "matched_all": len(matched_edges),
            "matched_core": len(matched_core_edges),
            "total_gt_core": total_gt_core_edges,
            "recall_all": (
                len(matched_edges) / total_gt_edges if total_gt_edges else 0
            ),
            "recall_core": (
                len(matched_core_edges) / total_gt_core_edges
                if total_gt_core_edges
                else 0
            ),
            "type_distribution": type_dist,
        },
        "tokens": extracted["tokens"],
    }
