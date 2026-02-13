"""
Edge schema definitions for knowledge graph.

MVP Edge Types (10):
- IsA: Type attribution (正方形 IsA 多边形)
- PartOf: Part-whole relation (边 PartOf 三角形)
- Causes: Causation (加热 Causes 水沸腾)
- Enables: Makes possible (氧气 Enables 燃烧)
- Prevents: Blocks/stops (绝缘体 Prevents 导电)
- Before: Temporal ordering (文艺复兴 Before 工业革命)
- HasProperty: Attribute (正方形 HasProperty 四条等边)
- Contrasts: Opposition/comparison (有理数 Contrasts 无理数)
- Supports: Argumentation support (化石证据 Supports 进化论)
- Attacks: Argumentation attack (反例 Attacks 假说)

Updated: 2026-02-12 - Added Enables, Prevents, Contrasts based on benchmark testing
Updated: 2026-02-12 - REMOVED RelatedTo (too generic, provides no information value)
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
    ENABLES = "Enables"    # Added 2026-02-12
    PREVENTS = "Prevents"  # Added 2026-02-12

    # Temporal
    BEFORE = "Before"

    # Attributive
    HAS_PROPERTY = "HasProperty"

    # Discourse
    CONTRASTS = "Contrasts"  # Added 2026-02-12

    # Argumentative
    SUPPORTS = "Supports"
    ATTACKS = "Attacks"

    # NOTE: RelatedTo was REMOVED on 2026-02-12
    # Reason: Too generic - if two nodes have an edge, they are obviously related.
    # This forced "fallback" option led to lazy classification (76% usage in tests).
    # Now: If no specific relation fits, DON'T create an edge.


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
