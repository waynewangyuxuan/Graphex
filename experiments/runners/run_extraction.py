"""Config-driven experiment runner: load YAML config → extract → resolve → save.

Usage:
    python experiments/runners/run_extraction.py experiments/configs/v5_flash_lite.yaml
"""

import argparse
import concurrent.futures
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
from src.chunking.chunker import Chunker
from src.extraction.structured_extractor import extract_chunk
from src.extraction.merger import merge_chunk_results


def run(config_path: str) -> None:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    exp = config["experiment"]
    ext = config["extraction"]
    res = config.get("resolution", {})

    print(f"\n{'='*60}")
    print(f"Experiment: {exp['name']}")
    print(f"Model: {ext['model']}")
    print(f"Chunk: {ext['chunk_size']} chars, overlap {ext['chunk_overlap']}")
    print(f"Resolution: {res.get('method', 'none')}")
    print(f"{'='*60}\n")

    # Resolve datasets
    datasets = config.get("evaluation", {}).get("datasets", ["threads-cv"])
    for dataset in datasets:
        pdf_path = project_root / "sample-files" / f"{dataset}.pdf"
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path} not found")
            continue

        # Parse
        parser = PDFParser()
        doc = parser.parse(pdf_path)
        print(f"Parsed: {doc.title} ({len(doc.content)} chars)")

        # Chunk
        chunker = Chunker(
            chunk_size=ext["chunk_size"],
            chunk_overlap=ext["chunk_overlap"],
        )
        chunks = chunker.chunk(doc.content, doc.document_id)
        print(f"Chunks: {len(chunks)}")

        # Extract (parallel)
        start_time = time.time()
        total = len(chunks)

        def _extract(idx_chunk):
            idx, chunk = idx_chunk
            result = extract_chunk(chunk.text, model=ext["model"])
            n = len(result["entities"])
            print(f"  chunk {idx+1}/{total} -> {n} entities")
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            chunk_results = list(pool.map(_extract, enumerate(chunks)))

        elapsed = time.time() - start_time
        print(f"Extraction: {elapsed:.1f}s")

        # Merge
        enable_llm = res.get("method", "none") != "none"
        merged = merge_chunk_results(
            chunk_results,
            enable_llm_layer=enable_llm,
        )
        print(f"After merge: {len(merged['entities'])} entities, "
              f"{len(merged['relationships'])} relationships")

        # Save
        result_dir = project_root / "experiments" / "results" / exp["name"]
        result_dir.mkdir(parents=True, exist_ok=True)
        output_path = result_dir / f"{dataset}_output.json"
        with open(output_path, "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Path to experiment config YAML")
    args = parser.parse_args()
    run(args.config)
