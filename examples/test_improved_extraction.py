#!/usr/bin/env python3
"""
Test improved extraction with new schema and prompts.

Tests the following improvements:
- New Method node type
- New edge types: Enables, Prevents, Contrasts
- Enhanced noise filtering
- Importance scoring
- Decision tree for edge type selection
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import Pipeline, PipelineConfig
from src.schema.graph import KnowledgeGraph


def analyze_graph(graph: KnowledgeGraph, name: str) -> dict:
    """Analyze extraction quality metrics."""

    # Count node types
    node_types = {}
    for node in graph.nodes.values():
        node_types[node.type.value] = node_types.get(node.type.value, 0) + 1

    # Count edge types
    edge_types = {}
    for edge in graph.edges.values():
        edge_types[edge.type.value] = edge_types.get(edge.type.value, 0) + 1

    # Calculate RelatedTo percentage
    total_edges = len(graph.edges)
    related_to_count = edge_types.get("RelatedTo", 0)
    related_to_pct = (related_to_count / total_edges * 100) if total_edges > 0 else 0

    # Check for noise entities (filenames, etc.)
    noise_patterns = ['.c', '.py', '.java', '.txt', '.pdf', '©']
    noise_entities = [
        node.label for node in graph.nodes.values()
        if any(pattern in node.label for pattern in noise_patterns)
    ]

    return {
        "name": name,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "node_types": node_types,
        "edge_types": edge_types,
        "related_to_pct": related_to_pct,
        "noise_entities": noise_entities,
    }


def print_analysis(results: dict):
    """Print detailed analysis."""
    print(f"\n{'='*60}")
    print(f"Analysis: {results['name']}")
    print(f"{'='*60}")

    print(f"\n## Summary")
    print(f"  Total Nodes: {results['total_nodes']}")
    print(f"  Total Edges: {results['total_edges']}")
    print(f"  RelatedTo%: {results['related_to_pct']:.1f}% {'✓ GOOD' if results['related_to_pct'] < 40 else '✗ TOO HIGH'}")

    print(f"\n## Node Types")
    for node_type, count in sorted(results['node_types'].items(), key=lambda x: -x[1]):
        pct = count / results['total_nodes'] * 100
        print(f"  {node_type:12} {count:3d} ({pct:5.1f}%)")

    print(f"\n## Edge Types")
    for edge_type, count in sorted(results['edge_types'].items(), key=lambda x: -x[1]):
        pct = count / results['total_edges'] * 100
        marker = "  "
        if edge_type == "RelatedTo":
            marker = "⚠️ " if pct >= 40 else "✓ "
        print(f"  {marker}{edge_type:12} {count:3d} ({pct:5.1f}%)")

    if results['noise_entities']:
        print(f"\n## ⚠️ Noise Entities Detected ({len(results['noise_entities'])})")
        for entity in results['noise_entities'][:10]:
            print(f"  - {entity}")
        if len(results['noise_entities']) > 10:
            print(f"  ... and {len(results['noise_entities']) - 10} more")
    else:
        print(f"\n## ✓ No Noise Entities Detected")


def test_sample_text():
    """Test with a sample text about algorithms."""

    sample_text = """
    # Sorting Algorithms

    Sorting is a fundamental operation in computer science. The most common
    sorting algorithms include QuickSort, MergeSort, and BubbleSort.

    ## QuickSort

    QuickSort is a divide-and-conquer algorithm invented by Tony Hoare in 1959.
    It works by selecting a pivot element and partitioning the array around it.
    QuickSort has average time complexity O(n log n), but worst-case O(n²).

    The choice of pivot greatly affects performance. A good pivot enables
    balanced partitioning, while a bad pivot can cause quadratic behavior.

    ## MergeSort vs QuickSort

    MergeSort guarantees O(n log n) time complexity in all cases, contrasting
    with QuickSort's variable performance. However, QuickSort is often faster
    in practice due to better cache locality.

    MergeSort requires O(n) extra space, while QuickSort can be implemented
    in-place. This memory overhead prevents MergeSort from being the default
    choice in many libraries.

    ## BubbleSort

    BubbleSort is a simple algorithm with O(n²) time complexity. It repeatedly
    compares adjacent elements and swaps them if needed. While easy to understand,
    its poor performance makes it unsuitable for large datasets.
    """

    config = PipelineConfig(
        chunk_size=1024,
        chunk_overlap=100,
        confidence_threshold=0.5,
    )

    print("="*60)
    print("Testing Improved Extraction Pipeline")
    print("="*60)
    print(f"Model: {config.model}")
    print(f"Text length: {len(sample_text)} chars")

    pipeline = Pipeline(config=config)

    start = time.time()
    graph = pipeline.run_text(sample_text, document_id="sorting_algorithms")
    elapsed = time.time() - start

    print(f"\nExtraction completed in {elapsed:.1f}s")

    # Analyze results
    results = analyze_graph(graph, "Sorting Algorithms")
    print_analysis(results)

    # Show sample entities
    print(f"\n## Sample Nodes (first 10)")
    for i, node in enumerate(list(graph.nodes.values())[:10], 1):
        print(f"{i:2d}. [{node.type.value:7}] {node.label}")
        if hasattr(node, 'importance'):
            print(f"     Importance: {getattr(node, 'importance', 'N/A')}")

    # Show sample relations
    print(f"\n## Sample Edges (first 10)")
    for i, edge in enumerate(list(graph.edges.values())[:10], 1):
        source = graph.get_node(edge.source_id)
        target = graph.get_node(edge.target_id)
        if source and target:
            print(f"{i:2d}. {source.label} --[{edge.type.value}]--> {target.label}")
            print(f"     Confidence: {edge.confidence:.2f}")

    # Save results
    output_path = Path("examples/output/test_improved_extraction.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.to_json(output_path)
    print(f"\nSaved to: {output_path}")

    return results


def test_pdf_comparison():
    """Test on existing PDF and compare with previous results."""

    pdf_path = Path("sample-files/threads-cv.pdf")
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return None

    config = PipelineConfig(
        chunk_size=1024,
        chunk_overlap=100,
        confidence_threshold=0.5,
    )

    print(f"\n{'='*60}")
    print(f"Testing on: {pdf_path.name}")
    print(f"{'='*60}")

    pipeline = Pipeline(config=config)

    start = time.time()
    graph = pipeline.run(pdf_path)
    elapsed = time.time() - start

    print(f"Extraction completed in {elapsed:.1f}s")

    # Analyze results
    results = analyze_graph(graph, pdf_path.name)
    print_analysis(results)

    # Save results
    output_path = Path("examples/output/threads-cv_improved.json")
    graph.to_json(output_path)
    print(f"\nSaved to: {output_path}")

    # Compare with previous results
    old_path = Path("examples/output/threads-cv_graph.json")
    if old_path.exists():
        print(f"\n## Comparison with Previous Extraction")
        old_graph = KnowledgeGraph.from_json(old_path)
        old_results = analyze_graph(old_graph, "Previous")

        print(f"\n  Nodes: {old_results['total_nodes']} → {results['total_nodes']}")
        print(f"  Edges: {old_results['total_edges']} → {results['total_edges']}")
        print(f"  RelatedTo%: {old_results['related_to_pct']:.1f}% → {results['related_to_pct']:.1f}%")

        if 'Method' in results['node_types']:
            print(f"  ✓ New: Method nodes = {results['node_types']['Method']}")

        new_edge_types = set(results['edge_types'].keys()) - set(old_results['edge_types'].keys())
        if new_edge_types:
            print(f"  ✓ New edge types: {', '.join(new_edge_types)}")

    return results


def main():
    """Run all tests."""

    print("\n" + "="*60)
    print("Improved Extraction Pipeline Test Suite")
    print("="*60)

    # Test 1: Sample text
    print("\n[Test 1/2] Sample text extraction...")
    test_sample_text()

    # Test 2: PDF comparison
    print("\n[Test 2/2] PDF extraction comparison...")
    test_pdf_comparison()

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()
