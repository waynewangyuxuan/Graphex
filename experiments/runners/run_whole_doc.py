"""Whole-document extraction: single LLM call, no chunking, no ER.

Usage:
    python experiments/runners/run_whole_doc.py [config.yaml]
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
from src.extraction.structured_extractor import extract_chunk
from src.evaluation.evaluator import evaluate_against_ground_truth


def run(
    pdf_path: Path,
    gt_path: Path,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    prompt: str = "whole_doc",
    experiment_name: str = "v6-whole-doc",
):
    print(f"\n{'='*60}")
    print(f"Whole-Document Extraction: {pdf_path.name}")
    print(f"Model: {model}")
    print(f"Prompt: {prompt}")
    print(f"{'='*60}\n")

    # Parse
    parser = PDFParser()
    doc = parser.parse(pdf_path)
    print(f"Parsed: {doc.title} ({doc.page_count} pages, {len(doc.content)} chars)")
    print(f"Estimated tokens: ~{len(doc.content) // 4}")

    # Extract — single call, whole document
    print(f"\nExtracting (single call, whole document)...")
    start = time.time()
    result = extract_chunk(doc.content, model=model, prompt=prompt)
    elapsed = time.time() - start

    n_ent = len(result["entities"])
    n_rel = len(result["relationships"])
    print(f"Done in {elapsed:.1f}s: {n_ent} entities, {n_rel} relationships")
    print(f"Tokens: input={result['tokens']['input']}, output={result['tokens']['output']}")

    # Wrap as merged format (no merge needed)
    merged = {
        "entities": result["entities"],
        "relationships": result["relationships"],
        "tokens": result["tokens"],
    }

    # Evaluate
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
        json.dump(merged, f, indent=2, ensure_ascii=False)
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
            model=ext["model"],
            prompt=ext.get("prompt", "whole_doc"),
            experiment_name=config["experiment"]["name"],
        )
    else:
        run(pdf_path, gt_path)
