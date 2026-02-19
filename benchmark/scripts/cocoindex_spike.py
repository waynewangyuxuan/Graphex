"""
CocoIndex-style Spike: Single-call structured extraction.

Simulates CocoIndex's ExtractByLlm approach:
- Define dataclasses for the output schema
- Single LLM call per chunk → entities + relationships
- No multi-agent pipeline, no FirstPass, no separate grounding step

Compare against ground truth to evaluate extraction quality vs current pipeline.
"""

import json
import sys
import time
import concurrent.futures
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import litellm
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from src.parsing.pdf_parser import PDFParser
from src.chunking.chunker import Chunker
from src.resolution.entity_resolver import EntityResolver
from src.resolution.parallel_merge import parallel_merge


# ============================================================
# CocoIndex-style Dataclass Schema
# (Mirrors what you'd define for cocoindex.functions.ExtractByLlm)
# ============================================================

ENTITY_TYPES = ["Concept", "Method", "Event", "Agent", "Claim", "Fact"]
EDGE_TYPES = [
    "IsA", "PartOf", "Causes", "Enables", "Prevents",
    "Before", "HasProperty", "Contrasts", "Supports", "Attacks",
]

EXTRACTION_INSTRUCTION = """You are extracting a knowledge graph from educational/technical text.

## Task
Extract entities and relationships that represent the **knowledge being taught**.

## Entity Types
- Concept: Abstract ideas being explained (e.g., "Condition Variable", "Bounded Buffer")
- Method: Operations/procedures being taught (e.g., "wait()", "signal()")
- Event: Historical events relevant to understanding
- Agent: People whose IDEAS are being taught (not authors/editors)
- Claim: Rules/best practices advocated (e.g., "Always use while loops")
- Fact: Verified factual statements

## Relationship Types
- IsA: A is a kind of B
- PartOf: A is part of B
- Causes: A causes B to happen
- Enables: A makes B possible
- Prevents: A blocks/stops B
- Before: A happens before B
- HasProperty: B is a property/attribute of A
- Contrasts: A and B are opposing/contrasting
- Supports: A provides evidence for B
- Attacks: A refutes/undermines B

## Rules
1. Only extract concepts the document is TEACHING, not just mentioning
2. Skip filenames, author names, code variable names unless they ARE the concept
3. Every relationship must have a specific type - if none fits, don't create it
4. Quality over quantity: fewer precise extractions > many vague ones
5. Assign importance: "core" (central to learning), "supporting" (background), "peripheral" (briefly mentioned)

## Output: Return ONLY valid JSON, no markdown fences.
{
  "entities": [
    {
      "id": "e1",
      "type": "Concept",
      "label": "Short Label",
      "definition": "Clear definition in 1-3 sentences.",
      "importance": "core"
    }
  ],
  "relationships": [
    {
      "source": "e1",
      "target": "e2",
      "type": "PartOf",
      "evidence": "brief text evidence"
    }
  ]
}"""


def extract_chunk_cocoindex_style(
    chunk_text: str,
    model: str = "gemini/gemini-2.0-flash",
) -> dict:
    """
    CocoIndex-style: single LLM call extracts BOTH entities and relationships.
    """
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_INSTRUCTION},
            {"role": "user", "content": chunk_text},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content
    tokens_used = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens,
    }

    # Parse JSON
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try extracting JSON from response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response_text[start:end])
        else:
            data = {"entities": [], "relationships": []}

    return {
        "entities": data.get("entities", []),
        "relationships": data.get("relationships", []),
        "tokens": tokens_used,
    }


def merge_chunk_results(chunk_results: list[dict], max_workers: int = 4) -> dict:
    """
    Merge results from multiple chunks using embedding-based entity resolution
    and parallel pairwise merge (O(log N) rounds).

    Replaces the previous simple label-dedup approach.
    Source: entity-resolution-module (iText2KG pattern, applied 2026-02-19).
    See: src/resolution/entity_resolver.py, src/resolution/parallel_merge.py
    """
    total_tokens = {
        "input": sum(r["tokens"]["input"] for r in chunk_results),
        "output": sum(r["tokens"]["output"] for r in chunk_results),
    }

    # Strip token metadata before passing to the merge pipeline
    kg_parts = [
        {"entities": r["entities"], "relationships": r["relationships"]}
        for r in chunk_results
    ]

    print("Initializing entity resolver (embedding model)...", end=" ", flush=True)
    resolver = EntityResolver()
    print("ready")

    merged_kg = parallel_merge(kg_parts, resolver, max_workers=max_workers)

    return {**merged_kg, "tokens": total_tokens}


def evaluate_against_ground_truth(
    extracted: dict,
    ground_truth_path: Path,
) -> dict:
    """
    Compare extracted results against ground truth.
    Uses fuzzy label matching for nodes and (source_label, target_label, type) for edges.
    """
    with open(ground_truth_path) as f:
        gt = json.load(f)

    gt_nodes = gt.get("nodes", {})
    gt_edges = gt.get("edges", {})

    # ---- Node matching ----
    gt_node_labels = {}  # normalized_label → node_info
    gt_core_labels = set()
    for nid, node in gt_nodes.items():
        if nid.startswith("_"):
            continue
        label = node.get("label", "").lower().strip()
        gt_node_labels[label] = node
        if node.get("importance") == "core":
            gt_core_labels.add(label)

    extracted_labels = set()
    for entity in extracted["entities"]:
        extracted_labels.add(entity.get("label", "").lower().strip())

    # Fuzzy matching: check if extracted label contains or is contained by GT label
    matched_all = set()
    matched_core = set()
    for ext_label in extracted_labels:
        for gt_label in gt_node_labels:
            if ext_label == gt_label or ext_label in gt_label or gt_label in ext_label:
                matched_all.add(gt_label)
                if gt_label in gt_core_labels:
                    matched_core.add(gt_label)

    total_gt_nodes = len([k for k in gt_nodes if not k.startswith("_")])
    total_gt_core = len(gt_core_labels)

    # ---- Edge matching ----
    # Build GT edge set: (source_label, target_label, type)
    gt_edge_set = set()
    gt_core_edge_set = set()
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

    # Build extracted edge set
    entity_id_to_label = {}
    for entity in extracted["entities"]:
        entity_id_to_label[entity.get("id", "")] = entity.get("label", "").lower().strip()

    extracted_edge_set = set()
    for rel in extracted["relationships"]:
        src_label = entity_id_to_label.get(rel.get("source", ""), rel.get("source", "").lower())
        tgt_label = entity_id_to_label.get(rel.get("target", ""), rel.get("target", "").lower())
        edge_type = rel.get("type", "")
        extracted_edge_set.add((src_label, tgt_label, edge_type))

    # Match edges (fuzzy on labels, exact on type)
    matched_edges = set()
    matched_core_edges = set()
    for ext_edge in extracted_edge_set:
        ext_src, ext_tgt, ext_type = ext_edge
        for gt_edge in gt_edge_set:
            gt_src, gt_tgt, gt_type = gt_edge
            src_match = ext_src == gt_src or ext_src in gt_src or gt_src in ext_src
            tgt_match = ext_tgt == gt_tgt or ext_tgt in gt_tgt or gt_tgt in ext_tgt
            type_match = ext_type == gt_type
            if src_match and tgt_match and type_match:
                matched_edges.add(gt_edge)
                if gt_edge in gt_core_edge_set:
                    matched_core_edges.add(gt_edge)

    total_gt_edges = len([k for k in gt_edges if not k.startswith("_")])
    total_gt_core_edges = len(gt_core_edge_set)

    # ---- Edge type distribution ----
    type_dist = {}
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
            "recall_all": len(matched_edges) / total_gt_edges if total_gt_edges else 0,
            "recall_core": len(matched_core_edges) / total_gt_core_edges if total_gt_core_edges else 0,
            "type_distribution": type_dist,
        },
        "tokens": extracted["tokens"],
    }


def run_spike(
    pdf_path: Path,
    ground_truth_path: Path,
    model: str = "gemini/gemini-2.0-flash",
    chunk_size: int = 512,
    chunk_overlap: int = 75,
    max_extract_workers: int = 8,
):
    """Run the full spike: parse → chunk → extract → evaluate."""

    print(f"\n{'='*60}")
    print(f"CocoIndex-style Spike: {pdf_path.name}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Parse
    parser = PDFParser()
    doc = parser.parse(pdf_path)
    print(f"Parsed: {doc.title} ({doc.page_count} pages, {len(doc.content)} chars)")

    # Chunk
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk(doc.content, doc.document_id)
    print(f"Chunks: {len(chunks)}")

    # Extract (CocoIndex-style: single call per chunk, PARALLEL)
    start_time = time.time()
    total_chunks = len(chunks)
    print(f"  Extracting {total_chunks} chunks in parallel (max_workers={max_extract_workers})...")

    def _extract_one(idx_chunk):
        idx, chunk = idx_chunk
        try:
            result = extract_chunk_cocoindex_style(chunk.text, model=model)
            n_ent = len(result["entities"])
            n_rel = len(result["relationships"])
            print(f"  ✓ chunk {idx+1}/{total_chunks} → {n_ent} entities, {n_rel} relationships")
            return result
        except Exception as e:
            print(f"  ✗ chunk {idx+1}/{total_chunks} → ERROR: {e}")
            return {"entities": [], "relationships": [], "tokens": {"input": 0, "output": 0}}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_extract_workers) as executor:
        chunk_results = list(executor.map(_extract_one, enumerate(chunks)))

    elapsed = time.time() - start_time
    print(f"\nExtraction completed in {elapsed:.1f}s ({total_chunks/elapsed:.1f} chunks/s)")

    # Merge
    merged = merge_chunk_results(chunk_results)
    print(f"After merge: {len(merged['entities'])} entities, {len(merged['relationships'])} relationships")
    print(f"Total tokens: {merged['tokens']}")

    # Evaluate
    evaluation = evaluate_against_ground_truth(merged, ground_truth_path)

    print(f"\n{'─'*40}")
    print("NODE RECALL")
    print(f"  All:  {evaluation['nodes']['matched_all']}/{evaluation['nodes']['total_gt']} = {evaluation['nodes']['recall_all']:.1%}")
    print(f"  Core: {evaluation['nodes']['matched_core']}/{evaluation['nodes']['total_gt_core']} = {evaluation['nodes']['recall_core']:.1%}")
    print(f"  Missed core: {evaluation['nodes']['missed_core']}")
    print(f"\nEDGE RECALL")
    print(f"  All:  {evaluation['edges']['matched_all']}/{evaluation['edges']['total_gt']} = {evaluation['edges']['recall_all']:.1%}")
    print(f"  Core: {evaluation['edges']['matched_core']}/{evaluation['edges']['total_gt_core']} = {evaluation['edges']['recall_core']:.1%}")
    print(f"  Type distribution: {evaluation['edges']['type_distribution']}")
    print(f"{'─'*40}")

    # Save results
    output_dir = ground_truth_path.parent
    output_file = output_dir / "cocoindex_spike_output.json"
    eval_file = output_dir / "cocoindex_spike_eval.json"

    with open(output_file, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    with open(eval_file, "w") as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to:")
    print(f"  {output_file}")
    print(f"  {eval_file}")

    return evaluation


if __name__ == "__main__":
    # Run on threads-cv benchmark
    pdf_path = project_root / "sample-files" / "threads-cv.pdf"
    gt_path = project_root / "benchmark" / "datasets" / "papers" / "threads-cv" / "ground_truth.json"

    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)
    if not gt_path.exists():
        print(f"ERROR: Ground truth not found at {gt_path}")
        sys.exit(1)

    run_spike(pdf_path, gt_path)
