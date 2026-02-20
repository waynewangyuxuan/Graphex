"""
Tests for schema definitions.
"""

import pytest

from src.schema.nodes import Node, NodeType, NodeSource, NodeMetadata, Granularity
from src.schema.edges import Edge, EdgeType, EdgeSource, ExtractionMethod
from src.schema.graph import KnowledgeGraph


class TestNode:
    """Tests for Node schema."""

    def test_create_node(self):
        """Test basic node creation."""
        node = Node(
            id="test_001",
            type=NodeType.CONCEPT,
            label="Test Concept",
            definition="This is a test concept for unit testing.",
            source=NodeSource(document_id="doc_001"),
        )

        assert node.id == "test_001"
        assert node.type == NodeType.CONCEPT
        assert node.label == "Test Concept"

    def test_node_with_metadata(self):
        """Test node with full metadata."""
        node = Node(
            id="test_002",
            type=NodeType.EVENT,
            label="Test Event",
            definition="An event that happened for testing purposes.",
            source=NodeSource(document_id="doc_001"),
            aliases=["TestEvent", "Testing Event"],
            metadata=NodeMetadata(
                granularity=Granularity.L3,
                confidence=0.95,
            ),
        )

        assert node.metadata.granularity == Granularity.L3
        assert node.metadata.confidence == 0.95
        assert len(node.aliases) == 2

    def test_node_types(self):
        """Test all node types are valid."""
        types = [NodeType.CONCEPT, NodeType.EVENT, NodeType.AGENT, NodeType.CLAIM, NodeType.FACT]
        assert len(types) == 5


class TestEdge:
    """Tests for Edge schema."""

    def test_create_edge(self):
        """Test basic edge creation."""
        edge = Edge(
            id="rel_001",
            source_id="entity_001",
            target_id="entity_002",
            type=EdgeType.CAUSES,
            source=EdgeSource(document_id="doc_001"),
        )

        assert edge.id == "rel_001"
        assert edge.type == EdgeType.CAUSES
        assert edge.is_directed is True

    def test_edge_types(self):
        """Test all edge types are valid."""
        types = [
            EdgeType.IS_A,
            EdgeType.PART_OF,
            EdgeType.CAUSES,
            EdgeType.ENABLES,
            EdgeType.PREVENTS,
            EdgeType.BEFORE,
            EdgeType.HAS_PROPERTY,
            EdgeType.CONTRASTS,
            EdgeType.SUPPORTS,
            EdgeType.ATTACKS,
        ]
        assert len(types) == 10


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph."""

    def test_create_empty_graph(self):
        """Test creating empty graph."""
        graph = KnowledgeGraph()
        assert len(graph) == 0
        assert len(graph.edges) == 0

    def test_add_node(self):
        """Test adding nodes to graph."""
        graph = KnowledgeGraph()
        node = Node(
            id="test_001",
            type=NodeType.CONCEPT,
            label="Test",
            definition="Test definition here.",
            source=NodeSource(document_id="doc_001"),
        )

        graph.add_node(node)
        assert len(graph) == 1
        assert graph.get_node("test_001") == node

    def test_add_edge(self):
        """Test adding edges to graph."""
        graph = KnowledgeGraph()

        # Add nodes first
        node1 = Node(
            id="entity_001",
            type=NodeType.CONCEPT,
            label="Concept A",
            definition="First concept.",
            source=NodeSource(document_id="doc_001"),
        )
        node2 = Node(
            id="entity_002",
            type=NodeType.CONCEPT,
            label="Concept B",
            definition="Second concept.",
            source=NodeSource(document_id="doc_001"),
        )
        graph.add_node(node1)
        graph.add_node(node2)

        # Add edge
        edge = Edge(
            id="rel_001",
            source_id="entity_001",
            target_id="entity_002",
            type=EdgeType.CAUSES,
            source=EdgeSource(document_id="doc_001"),
        )
        graph.add_edge(edge)

        assert len(graph.edges) == 1
        assert graph.get_edge("rel_001") == edge

    def test_add_edge_invalid_nodes(self):
        """Test adding edge with invalid node references."""
        graph = KnowledgeGraph()

        edge = Edge(
            id="rel_001",
            source_id="nonexistent_001",
            target_id="nonexistent_002",
            type=EdgeType.CAUSES,
            source=EdgeSource(document_id="doc_001"),
        )

        with pytest.raises(ValueError):
            graph.add_edge(edge)
