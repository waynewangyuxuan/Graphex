"""Two-pass extraction: entities (Lite) → relations (Flash).

Usage:
    python experiments/runners/run_two_pass.py [config.yaml]
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
from src.extraction.two_pass_extractor import extract_two_pass
from src.evaluation.evaluator import evaluate_against_ground_truth


def run(
    pdf_path: Path,
    gt_path: Path,
    entity_model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    relation_model: str = "gemini/gemini-2.5-flash",
    experiment_name: str = "v7-two-pass",
):
    print(f"\n{'='*60}")
    print(f"Two-Pass Extraction: {pdf_path.name}")
    print(f"Entity model:   {entity_model}")
    print(f"Relation model: {relation_model}")
    print(f"{'='*60}\n")

    # Parse
    parser = PDFParser()
    doc = parser.parse(pdf_path)
    print(f"Parsed: {doc.title} ({doc.page_count} pages, {len(doc.content)} chars)")
    print(f"Estimated tokens: ~{len(doc.content) // 4}")

    # Extract
    print(f"\nPass 1: Extracting entities ({entity_model})...")
    start = time.time()
    result = extract_two_pass(
        doc.content,
        entity_model=entity_model,
        relation_model=relation_model,
    )
    elapsed = time.time() - start

    n_ent = len(result["entities"])
    n_rel = len(result["relationships"])
    n_drop = len(result["dropped"])

    print(f"Done in {elapsed:.1f}s")
    print(f"  Entities: {n_ent}")
    print(f"  Relations: {n_rel} (dropped {n_drop} invalid)")
    print(f"  Tokens — Pass 1: in={result['tokens']['pass1_input']}, out={result['tokens']['pass1_output']}")
    print(f"  Tokens — Pass 2: in={result['tokens']['pass2_input']}, out={result['tokens']['pass2_output']}")
    print(f"  Total tokens: in={result['tokens']['input']}, out={result['tokens']['output']}")

    if result["dropped"]:
        print(f"\n  Dropped edges:")
        for d in result["dropped"]:
            rel = d["relationship"]
            print(f"    {rel.get('source','')} → {rel.get('target','')} [{rel.get('type','')}] — {d['issues']}")

    # Evaluate
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

    # Save
    result_dir = project_root / "experiments" / "results" / experiment_name
    result_dir.mkdir(parents=True, exist_ok=True)

    with open(result_dir / "threads-cv_output.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    with open(result_dir / "threads-cv_eval.json", "w") as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {result_dir}")
    return evaluation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", help="Path to experiment config YAML")
    args = parser.parse_args()

    pdf_path = project_root / "sample-files" / "threads-cv.pdf"
    gt_path = project_root / "benchmark" / "datasets" / "papers" / "threads-cv" / "ground_truth.json"

    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)

    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f)
        ext = config["extraction"]
        run(
            pdf_path, gt_path,
            entity_model=ext.get("entity_model", "gemini/gemini-2.5-flash-lite-preview-09-2025"),
            relation_model=ext.get("relation_model", "gemini/gemini-2.5-flash"),
            experiment_name=config["experiment"]["name"],
        )
    else:
        run(pdf_path, gt_path)
