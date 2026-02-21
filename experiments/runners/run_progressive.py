"""Progressive Understanding pipeline runner (ADR-0008).

Usage:
    python experiments/runners/run_progressive.py [config.yaml]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from src.parsing.pdf_parser import PDFParser
from src.extraction.progressive_extractor import extract_progressive
from src.evaluation.evaluator import evaluate_against_ground_truth


def run(
    pdf_path: Path,
    gt_path: Path,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    skip_consolidation: bool = False,
    experiment_name: str = "v8-progressive",
):
    print(f"\n{'='*60}")
    print(f"Progressive Understanding Pipeline: {pdf_path.name}")
    print(f"Model: {model}")
    print(f"Consolidation: {'SKIP' if skip_consolidation else 'ON'}")
    print(f"{'='*60}\n")

    # Parse PDF
    parser = PDFParser()
    doc = parser.parse(pdf_path)
    print(f"Parsed: {doc.title} ({doc.page_count} pages, {len(doc.content)} chars)")
    print(f"Estimated tokens: ~{len(doc.content) // 4}")

    # Run pipeline
    start = time.time()
    result = extract_progressive(
        doc.content,
        model=model,
        skip_consolidation=skip_consolidation,
    )
    elapsed = time.time() - start

    # ── Phase 0 report ──
    schema = result["phase0"]["schema"]
    print(f"\n--- Phase 0: Skim ({result['tokens']['phase0_input']}+{result['tokens']['phase0_output']} tokens) ---")
    print(f"  Topic: {schema.get('topic', '?')}")
    print(f"  Content type: {schema.get('content_type', '?')}")
    print(f"  Theme: {schema.get('theme', '?')[:100]}...")
    print(f"  Learning arc: {schema.get('narrative_root', {}).get('learning_arc', '?')}")
    print(f"  Expected core entities: {[e['label'] for e in schema.get('expected_core_entities', [])]}")

    # ── Chunking report ──
    chunking = result["chunking"]
    print(f"\n--- Chunking ({chunking['method']}) ---")
    print(f"  Chunks: {chunking['num_chunks']}")
    for c in chunking["chunks"]:
        print(f"    #{c['chunk_id']} [{c['section'][:50]}]: ~{c['token_estimate']} tokens")

    # ── Phase 1 report ──
    per_chunk = result["phase1"]["per_chunk"]
    print(f"\n--- Phase 1: Chunk Extraction ({result['tokens']['phase1_input']}+{result['tokens']['phase1_output']} tokens) ---")
    for pc in per_chunk:
        print(f"  Chunk {pc['chunk_id']} [{pc['section'][:40]}]: "
              f"+{pc['new_entities']} entities, +{pc['new_relationships']} rels, "
              f"{pc['dropped']} dropped")
        if pc.get("narrative_update"):
            print(f"    Narrative: {pc['narrative_update'][:100]}...")

    # ── Phase 2 report ──
    if result["phase2"]:
        p2 = result["phase2"]
        p2_in = result["tokens"].get("phase2_input", 0)
        p2_out = result["tokens"].get("phase2_output", 0)
        print(f"\n--- Phase 2: Consolidation ({p2_in}+{p2_out} tokens) ---")
        print(f"  Entity merges: {len(p2.get('entity_merges', []))}")
        for m in p2.get("entity_merges", []):
            print(f"    {m.get('remove_id')} → {m.get('keep_id')}: {m.get('reason', '')}")
        print(f"  New relationships: {len(p2.get('new_relationships', []))}")
        print(f"  Corrections: {len(p2.get('relationship_corrections', []))}")
        for c in p2.get("relationship_corrections", []):
            print(f"    {c.get('original_source')}→{c.get('original_target')} "
                  f"[{c.get('original_type')}] → "
                  f"{c.get('corrected_source')}→{c.get('corrected_target')} "
                  f"[{c.get('corrected_type')}]: {c.get('reason', '')}")

    # ── Summary ──
    n_ent = len(result["entities"])
    n_rel = len(result["relationships"])
    n_drop = len(result["dropped"])
    print(f"\n--- Summary (total {elapsed:.1f}s) ---")
    print(f"  Entities: {n_ent}")
    print(f"  Relationships: {n_rel} (dropped {n_drop} invalid)")
    print(f"  Total tokens: in={result['tokens']['input']}, out={result['tokens']['output']}")

    # Collect edge types used
    edge_types = {}
    for r in result["relationships"]:
        t = r.get("type", "?")
        edge_types[t] = edge_types.get(t, 0) + 1
    print(f"  Edge types used: {dict(sorted(edge_types.items(), key=lambda x: -x[1]))}")

    if result["dropped"]:
        print(f"\n  Dropped edges:")
        for d in result["dropped"][:10]:
            rel = d["relationship"]
            print(f"    {rel.get('source', '')} → {rel.get('target', '')} "
                  f"[{rel.get('type', '')}] — {d['issues']}")

    # ── Narrative ──
    narrative = result["phase1"]["narrative"]
    print(f"\n--- Narrative ({len(narrative)} parts) ---")
    for i, part in enumerate(narrative):
        label = "Root" if i == 0 else f"Chunk {i}"
        print(f"  [{label}] {part[:120]}...")

    # ── Evaluate ──
    if gt_path.exists():
        merged = {
            "entities": result["entities"],
            "relationships": result["relationships"],
            "tokens": result["tokens"],
        }
        evaluation = evaluate_against_ground_truth(merged, gt_path)

        print(f"\n{'~'*40}")
        print("NODE RECALL")
        n = evaluation["nodes"]
        print(f"  All:  {n['matched_all']}/{n['total_gt']} = {n['recall_all']:.1%}")
        print(f"  Core: {n['matched_core']}/{n['total_gt_core']} = {n['recall_core']:.1%}")
        print(f"  Missed core: {n['missed_core']}")
        print(f"\nEDGE RECALL")
        e = evaluation["edges"]
        print(f"  All:  {e['matched_all']}/{e['total_gt']} = {e['recall_all']:.1%}")
        print(f"  Core: {e['matched_core']}/{e['total_gt_core']} = {e['recall_core']:.1%}")
        print(f"  Types: {e['type_distribution']}")
        print(f"{'~'*40}")
    else:
        evaluation = None
        print(f"\n(No ground truth at {gt_path}, skipping evaluation)")

    # ── Save ──
    result_dir = project_root / "experiments" / "results" / experiment_name
    result_dir.mkdir(parents=True, exist_ok=True)

    doc_id = pdf_path.stem

    with open(result_dir / f"{doc_id}_output.json", "w") as f:
        save_result = {k: v for k, v in result.items() if k != "raw"}
        json.dump(save_result, f, indent=2, ensure_ascii=False)

    if evaluation:
        with open(result_dir / f"{doc_id}_eval.json", "w") as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {result_dir}")
    return result, evaluation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Progressive Understanding pipeline")
    parser.add_argument("config", nargs="?", help="Path to experiment config YAML")
    parser.add_argument("--no-consolidation", action="store_true",
                        help="Skip Phase 2 consolidation")
    args = parser.parse_args()

    pdf_path = project_root / "sample-files" / "threads-cv.pdf"
    gt_path = project_root / "benchmark" / "datasets" / "papers" / "threads-cv" / "ground_truth.json"

    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)

    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f)
        ext = config.get("extraction", {})
        run(
            pdf_path, gt_path,
            model=ext.get("model", "gemini/gemini-2.5-flash-lite-preview-09-2025"),
            skip_consolidation=ext.get("skip_consolidation", args.no_consolidation),
            experiment_name=config["experiment"]["name"],
        )
    else:
        run(
            pdf_path, gt_path,
            skip_consolidation=args.no_consolidation,
        )
