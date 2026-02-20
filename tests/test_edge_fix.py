"""
Test that edges can be added after entities are extracted.

Verifies that KnowledgeGraph.add_edge() correctly validates source/target
nodes exist, and that the correct pipeline order (add nodes before edges) works.
"""

import sys
sys.path.insert(0, '.')

import pytest
from src.schema.graph import KnowledgeGraph
from src.schema.nodes import Node, NodeType, NodeSource
from src.schema.edges import Edge, EdgeType, EdgeSource


def make_node(id: str, label: str, definition: str = 'Test definition') -> Node:
    """Helper to create test nodes."""
    return Node(
        id=id,
        type=NodeType.CONCEPT,
        label=label,
        definition=definition if len(definition) >= 10 else definition + ' - expanded',
        source=NodeSource(document_id='test'),
    )


def make_edge(id: str, source_id: str, target_id: str,
              edge_type: EdgeType = EdgeType.IS_A) -> Edge:
    """Helper to create test edges."""
    return Edge(
        id=id,
        source_id=source_id,
        target_id=target_id,
        type=edge_type,
        source=EdgeSource(document_id='test'),
    )


def test_add_edge_requires_nodes():
    """Test that add_edge fails if nodes don't exist."""
    graph = KnowledgeGraph()
    edge = make_edge('edge_001', 'entity_001', 'entity_002')

    with pytest.raises(ValueError, match="Source node entity_001 not found"):
        graph.add_edge(edge)


def test_add_edge_succeeds_with_nodes():
    """Test that add_edge succeeds when nodes exist."""
    graph = KnowledgeGraph()

    node1 = make_node('entity_001', 'Cond Variable', 'A synchronization primitive')
    node2 = make_node('entity_002', 'Mutex Lock', 'A mutual exclusion lock')

    graph.add_node(node1)
    graph.add_node(node2)

    edge = make_edge('edge_001', 'entity_001', 'entity_002', EdgeType.PART_OF)
    graph.add_edge(edge)

    assert len(graph.edges) == 1
    assert 'edge_001' in graph.edges


def test_pipeline_order_fix():
    """
    Verify the correct order: add nodes BEFORE extracting relations.

    This simulates the pipeline flow to verify edges can be added.
    """
    graph = KnowledgeGraph()

    # Step 1: Extract entities (simulated)
    entities = [
        make_node('e1', 'CV Concept', 'Condition Variable explanation'),
        make_node('e2', 'wait method', 'Wait method explanation'),
        make_node('e3', 'signal method', 'Signal method explanation'),
    ]

    # Step 2: THE FIX - Add entities to graph BEFORE relation extraction
    for entity in entities:
        if entity.id not in graph.nodes:
            graph.add_node(entity)

    # Step 3: Extract relations (simulated)
    edges = [
        make_edge('r1', 'e2', 'e1', EdgeType.PART_OF),
        make_edge('r2', 'e3', 'e1', EdgeType.PART_OF),
        make_edge('r3', 'e2', 'e3', EdgeType.CAUSES),
    ]

    # Step 4: Now edges can be added!
    for edge in edges:
        graph.add_edge(edge)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 3


if __name__ == '__main__':
    test_add_edge_requires_nodes()
    test_add_edge_succeeds_with_nodes()
    test_pipeline_order_fix()
    print('ALL TESTS PASSED')
