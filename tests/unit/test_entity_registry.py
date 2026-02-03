"""
Tests for entity registry.
"""

import pytest

from src.context.entity_registry import EntityRegistry
from src.schema.nodes import Node, NodeType, NodeSource


def create_test_node(id: str, label: str, node_type: NodeType = NodeType.CONCEPT) -> Node:
    """Helper to create test nodes."""
    return Node(
        id=id,
        type=node_type,
        label=label,
        definition=f"Definition of {label}",
        source=NodeSource(document_id="test_doc"),
    )


class TestEntityRegistry:
    """Tests for EntityRegistry."""

    def test_create_registry(self):
        """Test creating empty registry."""
        registry = EntityRegistry()
        assert len(registry) == 0

    def test_register_entity(self):
        """Test registering a new entity."""
        registry = EntityRegistry()
        node = create_test_node("entity_001", "Machine Learning")

        entity_id = registry.register(node)

        assert entity_id == "entity_001"
        assert len(registry) == 1
        assert registry.get("entity_001") == node

    def test_register_duplicate_label(self):
        """Test that duplicate labels return existing entity ID."""
        registry = EntityRegistry()
        node1 = create_test_node("entity_001", "Machine Learning")
        node2 = create_test_node("entity_002", "Machine Learning")

        id1 = registry.register(node1)
        id2 = registry.register(node2)

        assert id1 == "entity_001"
        assert id2 == "entity_001"  # Should return existing ID
        assert len(registry) == 1

    def test_get_by_label(self):
        """Test getting entity by label."""
        registry = EntityRegistry()
        node = create_test_node("entity_001", "Deep Learning")
        registry.register(node)

        result = registry.get_by_label("Deep Learning")
        assert result == node

        # Case insensitive
        result = registry.get_by_label("deep learning")
        assert result == node

    def test_get_relevant_to(self):
        """Test finding relevant entities."""
        registry = EntityRegistry()

        # Register some entities
        registry.register(create_test_node("e1", "Machine Learning"))
        registry.register(create_test_node("e2", "Deep Learning"))
        registry.register(create_test_node("e3", "Neural Networks"))
        registry.register(create_test_node("e4", "Python Programming"))

        # Find relevant to text mentioning ML
        text = "This paper discusses machine learning and deep learning."
        relevant = registry.get_relevant_to(text, limit=10)

        # Should find ML and DL related entities
        labels = [e.label.lower() for e in relevant]
        assert "machine learning" in labels
        assert "deep learning" in labels

    def test_all_entities(self):
        """Test getting all entities."""
        registry = EntityRegistry()

        nodes = [
            create_test_node("e1", "Entity 1"),
            create_test_node("e2", "Entity 2"),
            create_test_node("e3", "Entity 3"),
        ]

        for node in nodes:
            registry.register(node)

        all_entities = registry.all_entities()
        assert len(all_entities) == 3

    def test_find_similar(self):
        """Test finding similar entities."""
        registry = EntityRegistry()

        # Register base entity
        registry.register(create_test_node("e1", "Machine Learning Algorithm"))

        # Create similar entity
        similar = create_test_node("e2", "Machine Learning")

        found = registry.find_similar(similar)
        assert found is not None
        assert found.id == "e1"
