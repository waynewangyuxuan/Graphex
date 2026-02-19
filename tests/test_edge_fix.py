"""
Test that edges can be added after entities are extracted.

This test verifies the fix for the 0 edges bug where edges couldn't be added
because nodes weren't in the graph when add_edge was called.

Bug: In enhanced_pipeline.py, nodes were only added to the graph AFTER
Phase 3 (grounding verification), but edges were being added in Phase 2.
Since KnowledgeGraph.add_edge() validates that source/target nodes exist,
ALL edges were being rejected with ValueError.

Fix: Add nodes to graph immediately after extraction (in Phase 2),
before relation extraction runs. Nodes may still be filtered in Phase 3.
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


def test_filter_graph_removes_edges_to_filtered_nodes():
    """Test that _filter_graph correctly removes edges when nodes are filtered."""
    from src.pipeline.enhanced_pipeline import EnhancedPipeline, EnhancedPipelineConfig

    graph = KnowledgeGraph()

    # Add nodes
    for node in [
        make_node('e1', 'Node A', 'First node definition'),
        make_node('e2', 'Node B', 'Second node definition'),
        make_node('e3', 'Node C', 'Third node definition'),
    ]:
        graph.add_node(node)

    # Add edges
    for edge in [
        make_edge('r1', 'e1', 'e2', EdgeType.IS_A),
        make_edge('r2', 'e2', 'e3', EdgeType.PART_OF),
    ]:
        graph.add_edge(edge)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2

    # Simulate grounding verification: only e1 and e2 are verified
    verified_ids = {'e1', 'e2'}

    config = EnhancedPipelineConfig()
    pipeline = EnhancedPipeline(config)
    pipeline._filter_graph(graph, verified_ids)

    # e3 should be removed, and edge r2 (which references e3) should also be removed
    assert len(graph.nodes) == 2
    assert 'e1' in graph.nodes
    assert 'e2' in graph.nodes
    assert 'e3' not in graph.nodes

    assert len(graph.edges) == 1
    assert 'r1' in graph.edges  # e1 -> e2: both verified
    assert 'r2' not in graph.edges  # e2 -> e3: e3 not verified


if __name__ == '__main__':
    print('=' * 50)
    print('Testing the 0-edges bug fix')
    print('=' * 50)

    print('\nTest 1: add_edge should fail without nodes')
    try:
        graph = KnowledgeGraph()
        edge = make_edge('edge_001', 'entity_001', 'entity_002')
        graph.add_edge(edge)
        print('❌ FAILED')
    except ValueError:
        print('✅ PASSED')

    print('\nTest 2: add_edge should succeed with nodes')
    test_add_edge_succeeds_with_nodes()
    print('✅ PASSED')

    print('\nTest 3: Pipeline flow simulation')
    test_pipeline_order_fix()
    print('✅ PASSED')

    print('\nTest 4: _filter_graph removes edges correctly')
    test_filter_graph_removes_edges_to_filtered_nodes()
    print('✅ PASSED')

    print('\n' + '=' * 50)
    print('ALL TESTS PASSED!')
    print('=' * 50)
