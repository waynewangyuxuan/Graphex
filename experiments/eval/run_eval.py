"""Batch evaluation runner for narrative extraction pipeline.

Usage:
    # Download test papers
    python experiments/eval/run_eval.py --download

    # Run Phase 1 (CS papers)
    python experiments/eval/run_eval.py --phase 1

    # Run Phase 2 (cross-discipline)
    python experiments/eval/run_eval.py --phase 2

    # Run single document
    python experiments/eval/run_eval.py --doc attention

    # Run Phase 3 (multi-document) — requires multi-doc pipeline
    python experiments/eval/run_eval.py --phase 3
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from experiments.eval.test_corpus import (
    PHASE1_CS_PAPERS,
    PHASE2_CROSS_DISCIPLINE,
    PHASE3_MULTI_DOCUMENT,
    ALL_DOCS_BY_ID,
)
from experiments.eval.scoring_rubric import SCORE_TEMPLATE, compute_score


EVAL_DIR = project_root / "experiments" / "eval"
PAPERS_DIR = EVAL_DIR / "papers"
RESULTS_DIR = EVAL_DIR / "results"


# ── Download ─────────────────────────────────────────────────────────────

def download_papers(docs: list[dict]):
    """Download PDFs for evaluation."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)

    for doc in docs:
        pdf_path = PAPERS_DIR / f"{doc['id']}.pdf"
        if pdf_path.exists():
            print(f"  [skip] {doc['id']} — already downloaded")
            continue

        url = doc.get("url")
        if not url:
            print(f"  [manual] {doc['id']} — {doc.get('alt_source', 'provide PDF manually')}")
            continue

        print(f"  [download] {doc['id']} — {url}")
        try:
            subprocess.run(
                ["curl", "-L", "-o", str(pdf_path), url],
                check=True, timeout=60,
            )
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                print(f"    ✓ {pdf_path.stat().st_size // 1024} KB")
            else:
                print(f"    ✗ Download failed or too small")
                pdf_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"    ✗ Error: {e}")


# ── Run single document ──────────────────────────────────────────────────

def run_single(doc_id: str, model: str, parser_backend: str = "auto") -> dict | None:
    """Run pipeline on a single document and return results."""
    from src.extraction.narrative_extractor import extract_narrative
    from src.parsing.pdf_parser import create_parser

    doc_info = ALL_DOCS_BY_ID.get(doc_id)
    if not doc_info:
        print(f"Unknown doc: {doc_id}")
        return None

    pdf_path = PAPERS_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        print(f"  [skip] {doc_id} — PDF not found at {pdf_path}")
        return None

    print(f"\n{'─'*50}")
    print(f"Running: {doc_info['title']}")
    print(f"{'─'*50}")

    # Parse
    parser = create_parser(backend=parser_backend)
    doc = parser.parse(pdf_path)
    print(f"  Parsed ({parser_backend}): {len(doc.content)} chars, ~{len(doc.content)//4} tokens")

    # Extract
    start = time.time()
    result = extract_narrative(doc.content, model=model)
    elapsed = time.time() - start

    n_seg = len(result["segments"])
    n_rel = len(result["relations"])
    tree = result.get("tree", {})
    meta = tree.get("meta", {}) if tree else {}
    anchors = result.get("anchors", {})

    print(f"  Segments: {n_seg}")
    print(f"  Relations: {n_rel}")
    print(f"  Tree: {meta.get('spine_segments', '?')} spine / {meta.get('branch_segments', '?')} branch / {meta.get('acts', '?')} acts")
    print(f"  Anchors: {anchors.get('exact', 0)} exact, {anchors.get('fuzzy', 0)} fuzzy, {anchors.get('failed', 0)} failed")
    print(f"  Tokens: in={result['tokens']['input']}, out={result['tokens']['output']}")
    print(f"  Time: {elapsed:.1f}s")

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / f"{doc_id}_output.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {result_path}")

    # Generate score template
    template_path = RESULTS_DIR / f"{doc_id}_score.txt"
    if not template_path.exists():
        from datetime import date
        template = SCORE_TEMPLATE.format(
            doc_id=doc_id,
            doc_title=doc_info["title"],
            date=date.today().isoformat(),
        )
        with open(template_path, "w") as f:
            f.write(template)
        print(f"  Score template: {template_path}")

    return result


# ── Run phase ────────────────────────────────────────────────────────────

def run_phase(phase: int, model: str):
    """Run all documents for a given phase."""
    if phase == 1:
        docs = PHASE1_CS_PAPERS
        print(f"\n{'='*60}")
        print(f"PHASE 1: CS Papers ({len(docs)} documents)")
        print(f"{'='*60}")
    elif phase == 2:
        docs = PHASE2_CROSS_DISCIPLINE
        print(f"\n{'='*60}")
        print(f"PHASE 2: Cross-Discipline ({len(docs)} documents)")
        print(f"{'='*60}")
    elif phase == 3:
        print(f"\n{'='*60}")
        print(f"PHASE 3: Multi-Document")
        print(f"{'='*60}")
        run_multi_document(model)
        return
    else:
        print(f"Unknown phase: {phase}")
        return

    results_summary = []
    for doc in docs:
        result = run_single(doc["id"], model)
        if result:
            results_summary.append({
                "id": doc["id"],
                "title": doc["title"],
                "segments": len(result["segments"]),
                "relations": len(result["relations"]),
                "tree_spine": result.get("tree", {}).get("meta", {}).get("spine_segments", 0),
                "tree_branch": result.get("tree", {}).get("meta", {}).get("branch_segments", 0),
                "tokens_in": result["tokens"]["input"],
                "tokens_out": result["tokens"]["output"],
            })

    # Print summary table
    print(f"\n{'='*60}")
    print(f"PHASE {phase} SUMMARY")
    print(f"{'='*60}")
    print(f"{'Doc':<15} {'Seg':>4} {'Rel':>4} {'Spine':>6} {'Branch':>7} {'Tok In':>8} {'Tok Out':>8}")
    print(f"{'─'*15} {'─'*4} {'─'*4} {'─'*6} {'─'*7} {'─'*8} {'─'*8}")
    for r in results_summary:
        print(f"{r['id']:<15} {r['segments']:>4} {r['relations']:>4} "
              f"{r['tree_spine']:>6} {r['tree_branch']:>7} "
              f"{r['tokens_in']:>8} {r['tokens_out']:>8}")

    total_in = sum(r["tokens_in"] for r in results_summary)
    total_out = sum(r["tokens_out"] for r in results_summary)
    print(f"{'─'*15} {'─'*4} {'─'*4} {'─'*6} {'─'*7} {'─'*8} {'─'*8}")
    print(f"{'TOTAL':<15} {'':>4} {'':>4} {'':>6} {'':>7} {total_in:>8} {total_out:>8}")


# ── Phase 3: Multi-document ──────────────────────────────────────────────

def run_multi_document(model: str):
    """Run multi-document evaluation groups."""
    try:
        from src.extraction.multi_doc_extractor import extract_multi_document
    except ImportError:
        print("  Multi-document pipeline not yet implemented.")
        print("  Run Phase 1 & 2 first, then build multi-doc support.")
        return

    for group in PHASE3_MULTI_DOCUMENT:
        print(f"\n  Group: {group['title']}")
        print(f"  Docs: {group['doc_ids']}")

        # Check all single-doc results exist
        missing = []
        for doc_id in group["doc_ids"]:
            if not (RESULTS_DIR / f"{doc_id}_output.json").exists():
                missing.append(doc_id)
        if missing:
            print(f"  [skip] Missing single-doc results: {missing}")
            print(f"  Run Phase 1 first.")
            continue

        # Load single-doc results
        doc_results = {}
        for doc_id in group["doc_ids"]:
            with open(RESULTS_DIR / f"{doc_id}_output.json") as f:
                doc_results[doc_id] = json.load(f)

        # Run multi-doc extraction
        result = extract_multi_document(doc_results, model=model)

        # Save
        result_path = RESULTS_DIR / f"multi_{group['group_id']}_output.json"
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {result_path}")


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run pipeline evaluation")
    parser.add_argument("--phase", type=int, help="Run all docs for phase 1/2/3")
    parser.add_argument("--doc", type=str, help="Run single document by ID")
    parser.add_argument("--download", action="store_true", help="Download test papers")
    parser.add_argument("--model", default="gemini/gemini-2.5-flash-lite-preview-09-2025")
    parser.add_argument("--parser", default="auto", choices=["auto", "pymupdf", "marker"],
                        help="PDF parser backend (default: auto = marker if available)")
    args = parser.parse_args()

    if args.download:
        print("Downloading Phase 1 papers...")
        download_papers(PHASE1_CS_PAPERS)
        print("\nDownloading Phase 2 papers...")
        download_papers(PHASE2_CROSS_DISCIPLINE)
        print("\nDone. Check experiments/eval/papers/ for manual downloads needed.")
    elif args.doc:
        run_single(args.doc, args.model, parser_backend=args.parser)
    elif args.phase:
        run_phase(args.phase, args.model)  # TODO: pass parser_backend through run_phase
    else:
        print("Usage:")
        print("  --download        Download test papers")
        print("  --phase 1|2|3     Run all docs for a phase")
        print("  --doc <id>        Run single document")
        print("  --parser <backend> PDF parser: auto|pymupdf|marker")
