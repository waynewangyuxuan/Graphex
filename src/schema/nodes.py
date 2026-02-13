"""
Node schema definitions for knowledge graph.

MVP Node Types (6):
- Concept: Abstract concepts, theories, data structures
- Method: Operations, functions, APIs, algorithms
- Event: Things that happen with start/end time
- Agent: People/organizations who contributed to the content (NOT copyright/reference authors)
- Claim: Propositions, best practices, rules
- Fact: Verified factual statements

Updated: 2026-02-12 - Added Method type based on benchmark testing
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """MVP node types based on cognitive science research."""

    CONCEPT = "Concept"
    METHOD = "Method"  # Added 2026-02-12: for operations like wait(), signal()
    EVENT = "Event"
    AGENT = "Agent"
    CLAIM = "Claim"
    FACT = "Fact"


class Granularity(str, Enum):
    """Node granularity levels."""

    L1 = "L1"  # Atomic: single fact/proposition
    L2 = "L2"  # Component: concept/simple relation
    L3 = "L3"  # Chunk: topic/knowledge block
    L4 = "L4"  # Schema: complete framework/model


class TextSpan(BaseModel):
    """Reference to source text."""

    start: int
    end: int
    text: str


class NodeSource(BaseModel):
    """Source information for a node."""

    document_id: str
    text_span: Optional[TextSpan] = None


class NodeMetadata(BaseModel):
    """Node metadata."""

    granularity: Granularity = Granularity.L2
    abstraction_level: Optional[float] = Field(None, ge=0, le=1)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    created_at: Optional[str] = None


class Node(BaseModel):
    """
    Knowledge graph node.

    Represents a knowledge unit extracted from source documents.
    """

    id: str
    type: NodeType
    label: str = Field(..., min_length=1, max_length=50)
    definition: str = Field(..., min_length=10, max_length=500)
    source: NodeSource
    aliases: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return self.id == other.id
