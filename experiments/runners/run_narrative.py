"""Narrative Structure extraction runner.

Usage:
    python experiments/runners/run_narrative.py
"""

import argparse
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.parsing.pdf_parser import PDFParser
from src.extraction.narrative_extractor import extract_narrative


def run(
    pdf_path: Path,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    experiment_name: str = "v9-narrative",
):
    print(f"\n{'='*60}")
    print(f"Narrative Structure Extraction: {pdf_path.name}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Parse PDF
    parser = PDFParser()
    doc = parser.parse(pdf_path)
    print(f"Parsed: {doc.title} ({doc.page_count} pages, {len(doc.content)} chars)")
    print(f"Estimated tokens: ~{len(doc.content) // 4}")

    # Run pipeline
    start_time = time.time()
    result = extract_narrative(doc.content, model=model)
    elapsed = time.time() - start_time

    # ── Phase 0 report ──
    schema = result["phase0"]["schema"]
    print(f"\n--- Phase 0: Skim ({result['tokens']['phase0_input']}+{result['tokens']['phase0_output']} tokens) ---")
    print(f"  Topic: {schema.get('topic', '?')}")
    print(f"  Theme: {schema.get('theme', '?')[:120]}")
    print(f"  Key tension: {schema.get('key_tension', '?')[:120]}")
    print(f"  Learning arc: {schema.get('learning_arc', '?')}")
    print(f"  Key concepts: {schema.get('key_concepts', [])}")

    # ── Chunking report ──
    chunking = result["chunking"]
    print(f"\n--- Chunking ({chunking['method']}) ---")
    print(f"  Chunks: {chunking['num_chunks']}")
    for c in chunking["chunks"]:
        print(f"    #{c['chunk_id']}: ~{c['token_estimate']} tokens")

    # ── Phase 1 report ──
    per_chunk = result["phase1"]["per_chunk"]
    print(f"\n--- Phase 1: Narrative Extraction ({result['tokens']['phase1_input']}+{result['tokens']['phase1_output']} tokens) ---")
    for pc in per_chunk:
        print(f"  Chunk {pc['chunk_id']}: "
              f"+{pc['new_segments']} segments, +{pc['new_relations']} relations, "
              f"{pc['dropped']} dropped")

    # ── Segments ──
    segments = result["segments"]
    print(f"\n--- Segments ({len(segments)}) ---")
    for s in segments:
        concepts = ", ".join(c.get("label", "?") for c in s.get("concepts", []))
        print(f"  {s['id']} [{s.get('type', '?')}] \"{s.get('title', '?')}\"")
        print(f"       {s.get('content', '')[:120]}...")
        if concepts:
            print(f"       concepts: {concepts}")
        print()

    # ── Relations ──
    relations = result["relations"]
    print(f"--- Relations ({len(relations)}) ---")

    # Group by type
    rel_types = {}
    for r in relations:
        t = r.get("type", "?")
        rel_types[t] = rel_types.get(t, 0) + 1

    print(f"  Type distribution: {dict(sorted(rel_types.items(), key=lambda x: -x[1]))}")
    print()
    for r in relations:
        src = r.get("source", "?")
        tgt = r.get("target", "?")
        # Find segment titles
        src_title = next((s.get("title", "?") for s in segments if s["id"] == src), src)
        tgt_title = next((s.get("title", "?") for s in segments if s["id"] == tgt), tgt)
        print(f"  {src} → {tgt} [{r.get('type', '?')}]")
        print(f"       \"{src_title}\" → \"{tgt_title}\"")
        if r.get("annotation"):
            print(f"       {r['annotation'][:100]}")
        print()

    # ── Concept Index ──
    concept_index = result["concept_index"]
    print(f"--- Concept Index ({len(concept_index)} concepts) ---")
    for concept, refs in sorted(concept_index.items(), key=lambda x: -len(x[1])):
        roles = [f"{r['segment_id']}({r['role']})" for r in refs]
        print(f"  {concept}: {', '.join(roles)}")

    # ── Dropped ──
    if result["dropped"]:
        print(f"\n--- Dropped ({len(result['dropped'])}) ---")
        for d in result["dropped"][:10]:
            rel = d["relation"]
            print(f"  {rel.get('source', '')} → {rel.get('target', '')} "
                  f"[{rel.get('type', '')}] — {d['issues']}")

    # ── Summary ──
    n_seg = len(segments)
    n_rel = len(relations)
    n_drop = len(result["dropped"])
    n_concepts = len(concept_index)
    print(f"\n{'='*60}")
    print(f"SUMMARY ({elapsed:.1f}s)")
    print(f"  Segments: {n_seg}")
    print(f"  Relations: {n_rel} (dropped {n_drop})")
    print(f"  Concepts: {n_concepts}")
    print(f"  Tokens: in={result['tokens']['input']}, out={result['tokens']['output']}")

    # Segment type distribution
    seg_types = {}
    for s in segments:
        t = s.get("type", "?")
        seg_types[t] = seg_types.get(t, 0) + 1
    print(f"  Segment types: {dict(sorted(seg_types.items(), key=lambda x: -x[1]))}")
    print(f"  Relation types: {dict(sorted(rel_types.items(), key=lambda x: -x[1]))}")

    # Cross-chunk relations
    cross_chunk = 0
    for r in relations:
        src_chunk = next((s.get("_source_chunk") for s in segments if s["id"] == r.get("source")), None)
        tgt_chunk = next((s.get("_source_chunk") for s in segments if s["id"] == r.get("target")), None)
        if src_chunk and tgt_chunk and src_chunk != tgt_chunk:
            cross_chunk += 1
    print(f"  Cross-chunk relations: {cross_chunk}/{n_rel}")
    print(f"{'='*60}")

    # ── Save ──
    result_dir = project_root / "experiments" / "results" / experiment_name
    result_dir.mkdir(parents=True, exist_ok=True)

    doc_id = pdf_path.stem

    with open(result_dir / f"{doc_id}_output.json", "w") as f:
        save_result = {k: v for k, v in result.items() if k != "raw"}
        json.dump(save_result, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {result_dir / f'{doc_id}_output.json'}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Narrative Structure extraction")
    parser.add_argument("--model", default="gemini/gemini-2.5-flash-lite-preview-09-2025")
    args = parser.parse_args()

    pdf_path = project_root / "sample-files" / "threads-cv.pdf"

    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)

    run(pdf_path, model=args.model)
