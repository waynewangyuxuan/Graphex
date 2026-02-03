"""
Context builder for extraction.

Constructs context including schema, known entities, and recent extractions.
"""

from ..chunking.chunker import Chunk
from ..schema.nodes import Node, NodeType
from ..schema.edges import EdgeType
from .entity_registry import EntityRegistry


class ContextBuilder:
    """
    Build extraction context for agents.

    Combines schema info, known entities, and recent chunk results.
    """

    def __init__(self, entity_registry: EntityRegistry) -> None:
        """
        Initialize context builder.

        Args:
            entity_registry: Registry of known entities
        """
        self.registry = entity_registry
        self.recent_chunks: list[Chunk] = []
        self.max_recent_chunks = 2

    def add_chunk_result(self, chunk: Chunk) -> None:
        """
        Add a processed chunk to recent history.

        Args:
            chunk: Processed chunk with extraction results
        """
        self.recent_chunks.append(chunk)
        if len(self.recent_chunks) > self.max_recent_chunks:
            self.recent_chunks.pop(0)

    def build_entity_extraction_context(
        self, chunk: Chunk, max_entities: int = 20
    ) -> str:
        """
        Build context for entity extraction.

        Args:
            chunk: Current chunk to process
            max_entities: Maximum known entities to include

        Returns:
            Formatted context string
        """
        parts = []

        # Schema info
        parts.append(self._format_node_schema())

        # Known entities relevant to this chunk
        relevant = self.registry.get_relevant_to(chunk.text, limit=max_entities)
        if relevant:
            parts.append(self._format_known_entities(relevant))

        # Recent extraction results
        if self.recent_chunks:
            parts.append(self._format_recent_extractions())

        return "\n\n".join(parts)

    def build_relation_extraction_context(
        self, chunk: Chunk, entities: list[Node]
    ) -> str:
        """
        Build context for relation extraction.

        Args:
            chunk: Current chunk
            entities: Entities extracted from this chunk

        Returns:
            Formatted context string
        """
        parts = []

        # Edge schema
        parts.append(self._format_edge_schema())

        # Current entities
        parts.append(self._format_entities_for_relations(entities))

        return "\n\n".join(parts)

    def _format_node_schema(self) -> str:
        """Format node type schema."""
        lines = ["## Node Types (Entity Schema)\n"]
        for node_type in NodeType:
            lines.append(f"- **{node_type.value}**")
        return "\n".join(lines)

    def _format_edge_schema(self) -> str:
        """Format edge type schema."""
        lines = ["## Edge Types (Relation Schema)\n"]
        for edge_type in EdgeType:
            lines.append(f"- **{edge_type.value}**")
        return "\n".join(lines)

    def _format_known_entities(self, entities: list[Node]) -> str:
        """Format known entities list."""
        lines = ["## Known Entities (avoid duplicates)\n"]
        for entity in entities:
            lines.append(
                f"- {entity.id} [{entity.type.value}]: {entity.label}"
            )
        return "\n".join(lines)

    def _format_entities_for_relations(self, entities: list[Node]) -> str:
        """Format entities for relation extraction."""
        lines = ["## Entities in Current Chunk\n"]
        for entity in entities:
            lines.append(
                f"- **{entity.id}** [{entity.type.value}]: {entity.label}\n"
                f"  {entity.definition[:100]}..."
            )
        return "\n".join(lines)

    def _format_recent_extractions(self) -> str:
        """Format recent extraction results."""
        lines = ["## Recent Extractions (context)\n"]
        for chunk in self.recent_chunks:
            lines.append(f"### Chunk {chunk.id}")
            if chunk.extracted_entities:
                lines.append(f"  Entities: {', '.join(chunk.extracted_entities[:5])}")
            if chunk.extracted_relations:
                lines.append(f"  Relations: {len(chunk.extracted_relations)} found")
        return "\n".join(lines)
