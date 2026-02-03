"""
Pipeline state management.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..chunking.chunker import Chunk
from ..schema.graph import KnowledgeGraph
from ..context.entity_registry import EntityRegistry


class PipelineStage(Enum):
    """Pipeline execution stages."""

    INIT = "init"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    POST_PROCESSING = "post_processing"
    BUILDING_GRAPH = "building_graph"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PipelineState:
    """
    Pipeline execution state.

    Tracks progress through extraction stages.
    """

    stage: PipelineStage = PipelineStage.INIT
    document_id: Optional[str] = None

    # Processing state
    chunks: list[Chunk] = field(default_factory=list)
    current_chunk_index: int = 0
    entity_registry: EntityRegistry = field(default_factory=EntityRegistry)

    # Output
    graph: KnowledgeGraph = field(default_factory=KnowledgeGraph)

    # Tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_log: list[str] = field(default_factory=list)

    # Metrics
    total_entities: int = 0
    total_relations: int = 0
    chunks_processed: int = 0

    def log(self, message: str) -> None:
        """Add a log message."""
        self.processing_log.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.log(f"ERROR: {error}")

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
        self.log(f"WARNING: {warning}")

    def advance_to(self, stage: PipelineStage) -> None:
        """Advance to a new stage."""
        self.log(f"Stage: {self.stage.value} → {stage.value}")
        self.stage = stage

    def summary(self) -> dict:
        """Return a summary of the pipeline state."""
        return {
            "stage": self.stage.value,
            "document_id": self.document_id,
            "chunks_total": len(self.chunks),
            "chunks_processed": self.chunks_processed,
            "entities": self.total_entities,
            "relations": self.total_relations,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }
