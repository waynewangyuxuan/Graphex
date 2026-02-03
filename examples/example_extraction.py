"""
Example: Extract knowledge graph from text.

This example demonstrates the basic usage of Graphex pipeline.
"""

from src.pipeline import Pipeline, PipelineConfig
from src.schema.graph import KnowledgeGraph


def main():
    """Run example extraction."""

    # Sample text about machine learning
    sample_text = """
    # Introduction to Machine Learning

    Machine learning is a subset of artificial intelligence that enables
    computers to learn from data without being explicitly programmed.

    ## Types of Machine Learning

    There are three main types of machine learning:

    1. Supervised Learning: The algorithm learns from labeled training data.
       Examples include classification and regression tasks.

    2. Unsupervised Learning: The algorithm finds patterns in unlabeled data.
       Clustering and dimensionality reduction are common applications.

    3. Reinforcement Learning: The agent learns by interacting with an
       environment and receiving rewards or penalties.

    ## Applications

    Machine learning powers many modern technologies:
    - Natural language processing enables chatbots and translation
    - Computer vision allows image recognition and autonomous vehicles
    - Recommendation systems suggest products and content

    Deep learning, a subset of machine learning using neural networks,
    has achieved remarkable results in these areas.
    """

    # Configure pipeline
    config = PipelineConfig(
        chunk_size=256,  # Smaller chunks for this example
        chunk_overlap=50,
        confidence_threshold=0.6,
    )

    # Create pipeline
    pipeline = Pipeline(config=config)

    # Run extraction
    print("Extracting knowledge graph from sample text...")
    graph = pipeline.run_text(sample_text, document_id="ml_intro")

    # Display results
    print(f"\n{graph.summary()}")

    print("\n## Nodes (Entities)")
    for node in graph.nodes.values():
        print(f"  - [{node.type.value}] {node.label}")
        print(f"    {node.definition[:80]}...")

    print("\n## Edges (Relations)")
    for edge in graph.edges.values():
        source = graph.get_node(edge.source_id)
        target = graph.get_node(edge.target_id)
        if source and target:
            print(f"  - {source.label} --[{edge.type.value}]--> {target.label}")

    # Save to file
    from pathlib import Path

    output_path = Path("examples/output/ml_graph.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.to_json(output_path)
    print(f"\nGraph saved to {output_path}")


if __name__ == "__main__":
    main()
