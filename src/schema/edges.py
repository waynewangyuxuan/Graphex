"""
Edge schema definitions for knowledge graph.

MVP Edge Types (8):
- IsA: Type attribution (Dog IsA Mammal)
- PartOf: Part-whole relation (Engine PartOf Car)
- Causes: Causation (Rain Causes WetRoad)
- Before: Temporal ordering (EventA Before EventB)
- HasProperty: Attribute (Ice HasProperty Cold)
- Supports: Argumentation support (Evidence Supports Claim)
- Attacks: Argumentation attack (CounterExample Attacks Claim)
- RelatedTo: Generic association (fallback)
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """MVP edge types based on cognitive science research."""

    # Taxonomic
    IS_A = "IsA"

    # Compositional
    PART_OF = "PartOf"

    # Causal
    CAUSES = "Causes"

    # Temporal
    BEFORE = "Before"

    # Attributive
    HAS_PROPERTY = "HasProperty"

    # Argumentative
    SUPPORTS = "Supports"
    ATTACKS = "Attacks"

    # Associative (fallback)
    RELATED_TO = "RelatedTo"


class ExtractionMethod(str, Enum):
    """How the edge was extracted."""

    EXPLICIT = "explicit"  # Directly stated in text
    IMPLICIT = "implicit"  # Implied by context
    INFERRED = "inferred"  # Derived through reasoning


class EdgeSource(BaseModel):
    """Source information for an edge."""

    document_id: str
    extraction_method: ExtractionMethod = ExtractionMethod.EXPLICIT
    text_span: Optional["TextSpan"] = None


class TextSpan(BaseModel):
    """Reference to source text."""

    start: int
    end: int
    text: str


# Update forward reference
EdgeSource.model_rebuild()


class EdgeMetadata(BaseModel):
    """Edge metadata."""

    created_at: Optional[str] = None


class Edge(BaseModel):
    """
    Knowledge graph edge.

    Represents a relationship between two nodes.
    """

    id: str
    source_id: str  # Source node ID
    target_id: str  # Target node ID
    type: EdgeType
    is_directed: bool = True
    strength: Optional[float] = Field(None, ge=0, le=1)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    source: EdgeSource
    annotation: Optional[str] = None
    metadata: EdgeMetadata = Field(default_factory=EdgeMetadata)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Edge):
            return False
        return self.id == other.id
