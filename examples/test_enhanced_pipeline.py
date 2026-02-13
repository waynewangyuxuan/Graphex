#!/usr/bin/env python3
"""
Test script for the Enhanced Three-Phase Pipeline.

This script demonstrates the difference between the basic and enhanced pipelines.
"""

import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline import EnhancedPipeline, EnhancedPipelineConfig


def test_enhanced_pipeline(input_path: Path, output_path: Path):
    """Run the enhanced pipeline on a document."""

    print("=" * 60)
    print("Enhanced Three-Phase Pipeline Test")
    print("=" * 60)

    # Configure pipeline
    config = EnhancedPipelineConfig(
        chunk_size=1000,
        chunk_overlap=100,
        first_pass_sample_size=4000,
        enable_grounding_verification=True,
        grounding_min_confidence=0.6,
    )

    # Initialize pipeline
    pipeline = EnhancedPipeline(config)

    print(f"\nInput: {input_path}")
    print(f"Model: {config.model}")
    print(f"Grounding verification: {config.enable_grounding_verification}")
    print("-" * 60)

    # Run pipeline
    print("\nRunning pipeline...")
    graph = pipeline.run(input_path)

    # Output results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nNodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")

    # Node type distribution
    print("\nNode Types:")
    type_counts = {}
    for node in graph.nodes.values():
        t = node.type.value
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")

    # Edge type distribution
    print("\nEdge Types:")
    edge_counts = {}
    for edge in graph.edges.values():
        t = edge.type.value
        edge_counts[t] = edge_counts.get(t, 0) + 1
    for t, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")

    # List nodes
    print("\nExtracted Nodes:")
    for node in graph.nodes.values():
        print(f"  - [{node.type.value}] {node.label}")

    # Save to JSON
    output_data = {
        "nodes": {
            node.id: {
                "id": node.id,
                "type": node.type.value,
                "label": node.label,
                "definition": node.definition,
            }
            for node in graph.nodes.values()
        },
        "edges": {
            edge.id: {
                "id": edge.id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "type": edge.type.value,
                "confidence": edge.confidence,
            }
            for edge in graph.edges.values()
        },
        "metadata": {
            "pipeline": "EnhancedPipeline",
            "grounding_verification": config.enable_grounding_verification,
        },
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nOutput saved to: {output_path}")

    return graph


def main():
    # Default test file
    base_dir = Path(__file__).parent.parent
    test_file = base_dir / "benchmark/datasets/papers/threads-cv/threads-cv.pdf"
    output_file = base_dir / "examples/output/threads-cv_enhanced.json"

    # Allow custom input
    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not test_file.exists():
        print(f"Error: File not found: {test_file}")
        print("\nUsage: python test_enhanced_pipeline.py [input_file] [output_file]")
        sys.exit(1)

    test_enhanced_pipeline(test_file, output_file)


if __name__ == "__main__":
    main()
