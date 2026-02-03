"""
Entity registry for cross-chunk entity management.

Handles entity deduplication and resolution across chunks.
"""

from typing import Optional

from ..schema.nodes import Node


class EntityRegistry:
    """
    Global entity registry for cross-chunk entity management.

    Tracks entities and their aliases to prevent duplicates.
    """

    def __init__(self, similarity_threshold: float = 0.9) -> None:
        """
        Initialize registry.

        Args:
            similarity_threshold: Threshold for considering entities similar
        """
        self.entities: dict[str, Node] = {}
        self.aliases: dict[str, str] = {}  # alias label -> canonical id
        self.similarity_threshold = similarity_threshold

    def register(self, entity: Node) -> str:
        """
        Register a new entity or return existing ID if duplicate.

        Args:
            entity: Entity to register

        Returns:
            ID of the registered or existing entity
        """
        # Check exact match by label
        normalized_label = self._normalize_label(entity.label)
        if normalized_label in self.aliases:
            return self.aliases[normalized_label]

        # Check for similar existing entity
        similar = self.find_similar(entity)
        if similar:
            # Add as alias
            self.aliases[normalized_label] = similar.id
            return similar.id

        # Register as new entity
        self.entities[entity.id] = entity
        self.aliases[normalized_label] = entity.id

        return entity.id

    def find_similar(self, entity: Node) -> Optional[Node]:
        """
        Find a similar existing entity.

        Uses simple label matching for MVP.
        TODO: Add embedding-based similarity.

        Args:
            entity: Entity to match

        Returns:
            Similar entity if found, None otherwise
        """
        normalized = self._normalize_label(entity.label)

        for existing in self.entities.values():
            existing_normalized = self._normalize_label(existing.label)

            # Simple substring matching
            if normalized in existing_normalized or existing_normalized in normalized:
                return existing

            # Same type and high label overlap
            if entity.type == existing.type:
                overlap = self._label_overlap(normalized, existing_normalized)
                if overlap > self.similarity_threshold:
                    return existing

        return None

    def get(self, entity_id: str) -> Optional[Node]:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def get_by_label(self, label: str) -> Optional[Node]:
        """Get entity by label (or alias)."""
        normalized = self._normalize_label(label)
        if normalized in self.aliases:
            entity_id = self.aliases[normalized]
            return self.entities.get(entity_id)
        return None

    def get_relevant_to(self, text: str, limit: int = 20) -> list[Node]:
        """
        Get entities relevant to the given text.

        Simple keyword matching for MVP.
        TODO: Add embedding-based relevance.

        Args:
            text: Text to find relevant entities for
            limit: Maximum number of entities to return

        Returns:
            List of relevant entities
        """
        text_lower = text.lower()
        scored: list[tuple[Node, int]] = []

        for entity in self.entities.values():
            score = 0
            if entity.label.lower() in text_lower:
                score += 10
            for alias in entity.aliases:
                if alias.lower() in text_lower:
                    score += 5

            if score > 0:
                scored.append((entity, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [entity for entity, _ in scored[:limit]]

    def all_entities(self) -> list[Node]:
        """Return all registered entities."""
        return list(self.entities.values())

    def _normalize_label(self, label: str) -> str:
        """Normalize label for comparison."""
        return label.lower().strip()

    def _label_overlap(self, label1: str, label2: str) -> float:
        """Calculate word overlap ratio between labels."""
        words1 = set(label1.split())
        words2 = set(label2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def __len__(self) -> int:
        return len(self.entities)
