"""
Node schema definitions for knowledge graph.

MVP Node Types (5):
- Concept: Abstract concepts or categories
- Event: Things that happen with start/end time
- Agent: Conscious actors (people, organizations)
- Claim: Propositions that can be true/false
- Fact: Verified factual statements
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """MVP node types based on cognitive science research."""

    CONCEPT = "Concept"
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
