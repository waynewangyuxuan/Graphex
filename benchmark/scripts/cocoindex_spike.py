"""
CocoIndex-style Spike: quick-run benchmark script.

Thin wrapper around src/extraction/ and src/evaluation/ modules.
For config-driven experiments, use experiments/runners/run_extraction.py instead.
"""

import concurrent.futures
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from src.parsing.pdf_parser import PDFParser
from src.chunking.chunker import Chunker
from src.extraction.structured_extractor import extract_chunk
from src.extraction.merger import merge_chunk_results
from src.evaluation.evaluator import evaluate_against_ground_truth


def run_spike(
    pdf_path: Path,
    ground_truth_path: Path,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    chunk_size: int = 6000,
    chunk_overlap: int = 900,
    max_extract_workers: int = 8,
):
    """Run the full spike: parse -> chunk -> extract -> merge -> evaluate."""

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

    # Extract (parallel)
    start_time = time.time()
    total_chunks = len(chunks)
    print(f"  Extracting {total_chunks} chunks in parallel (max_workers={max_extract_workers})...")

    def _extract_one(idx_chunk):
        idx, chunk = idx_chunk
        try:
            result = extract_chunk(chunk.text, model=model)
            n_ent = len(result["entities"])
            n_rel = len(result["relationships"])
            print(f"  chunk {idx+1}/{total_chunks} -> {n_ent} entities, {n_rel} relationships")
            return result
        except Exception as e:
            print(f"  chunk {idx+1}/{total_chunks} -> ERROR: {e}")
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

    print(f"\n{'~'*40}")
    print("NODE RECALL")
    print(f"  All:  {evaluation['nodes']['matched_all']}/{evaluation['nodes']['total_gt']} = {evaluation['nodes']['recall_all']:.1%}")
    print(f"  Core: {evaluation['nodes']['matched_core']}/{evaluation['nodes']['total_gt_core']} = {evaluation['nodes']['recall_core']:.1%}")
    print(f"  Missed core: {evaluation['nodes']['missed_core']}")
    print(f"\nEDGE RECALL")
    print(f"  All:  {evaluation['edges']['matched_all']}/{evaluation['edges']['total_gt']} = {evaluation['edges']['recall_all']:.1%}")
    print(f"  Core: {evaluation['edges']['matched_core']}/{evaluation['edges']['total_gt_core']} = {evaluation['edges']['recall_core']:.1%}")
    print(f"  Type distribution: {evaluation['edges']['type_distribution']}")
    print(f"{'~'*40}")

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
    pdf_path = project_root / "sample-files" / "threads-cv.pdf"
    gt_path = project_root / "benchmark" / "datasets" / "papers" / "threads-cv" / "ground_truth.json"

    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)
    if not gt_path.exists():
        print(f"ERROR: Ground truth not found at {gt_path}")
        sys.exit(1)

    run_spike(pdf_path, gt_path)
