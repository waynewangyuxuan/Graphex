#!/usr/bin/env python3
"""
Test PDF extraction pipeline with sample files.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import Pipeline, PipelineConfig
from src.schema.graph import KnowledgeGraph


def test_pdf(pdf_path: Path, output_dir: Path) -> dict:
    """
    Test extraction on a single PDF.

    Returns:
        dict with results summary
    """
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path.name}")
    print(f"{'='*60}")

    config = PipelineConfig(
        chunk_size=512,
        chunk_overlap=75,
        confidence_threshold=0.6,
    )

    pipeline = Pipeline(config=config)

    start_time = time.time()

    try:
        graph = pipeline.run(pdf_path)
        elapsed = time.time() - start_time

        # Display results
        print(f"\n{graph.summary()}")

        print(f"\n## Nodes ({len(graph.nodes)} entities)")
        for node in list(graph.nodes.values())[:10]:  # Show first 10
            print(f"  - [{node.type.value}] {node.label}")
            if node.definition:
                print(f"    {node.definition[:60]}...")

        if len(graph.nodes) > 10:
            print(f"  ... and {len(graph.nodes) - 10} more")

        print(f"\n## Edges ({len(graph.edges)} relations)")
        shown = 0
        for edge in list(graph.edges.values())[:10]:  # Show first 10
            source = graph.get_node(edge.source_id)
            target = graph.get_node(edge.target_id)
            if source and target:
                print(f"  - {source.label} --[{edge.type.value}]--> {target.label}")
                shown += 1

        if len(graph.edges) > shown:
            print(f"  ... and {len(graph.edges) - shown} more")

        # Save to file
        output_path = output_dir / f"{pdf_path.stem}_graph.json"
        graph.to_json(output_path)
        print(f"\nGraph saved to: {output_path}")
        print(f"Time elapsed: {elapsed:.1f}s")

        return {
            "file": pdf_path.name,
            "success": True,
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "time": elapsed,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

        return {
            "file": pdf_path.name,
            "success": False,
            "error": str(e),
            "time": elapsed,
        }


def main():
    """Run tests on all sample PDFs."""

    sample_dir = Path(__file__).parent.parent / "sample-files"
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = [
        sample_dir / "MiroThinker.pdf",
        sample_dir / "threads-bugs.pdf",
        sample_dir / "threads-cv.pdf",
    ]

    # Check files exist
    for pdf in pdf_files:
        if not pdf.exists():
            print(f"Warning: {pdf} not found")

    print("=" * 60)
    print("Graphex PDF Extraction Test")
    print("=" * 60)
    print(f"Testing {len(pdf_files)} PDF files")
    print(f"Output directory: {output_dir}")

    results = []

    for pdf_path in pdf_files:
        if pdf_path.exists():
            result = test_pdf(pdf_path, output_dir)
            results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for r in results:
        status = "✓" if r["success"] else "✗"
        if r["success"]:
            print(f"{status} {r['file']}: {r['nodes']} nodes, {r['edges']} edges ({r['time']:.1f}s)")
        else:
            print(f"{status} {r['file']}: {r['error']} ({r['time']:.1f}s)")

    total_nodes = sum(r.get("nodes", 0) for r in results)
    total_edges = sum(r.get("edges", 0) for r in results)
    total_time = sum(r["time"] for r in results)
    success_count = sum(1 for r in results if r["success"])

    print(f"\nTotal: {success_count}/{len(results)} succeeded")
    print(f"Total extractions: {total_nodes} nodes, {total_edges} edges")
    print(f"Total time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
