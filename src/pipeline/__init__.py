"""
Pipeline orchestration.

Two pipeline options:

1. Pipeline (basic):
   PDF → Parse → Chunk → Extract Entities → Extract Relations → Validate → Graph

2. EnhancedPipeline (three-phase):
   PDF → Parse → Chunk →
     Phase 1: First-Pass (understand document) →
     Phase 2: Guided Extraction (use First-Pass context) →
     Phase 3: Grounding Verification (filter ungrounded) →
   Validate → Graph
"""

from .pipeline import Pipeline, PipelineConfig
from .enhanced_pipeline import EnhancedPipeline, EnhancedPipelineConfig
from .state import PipelineState, PipelineStage

__all__ = [
    # Basic pipeline
    "Pipeline",
    "PipelineConfig",
    # Enhanced three-phase pipeline
    "EnhancedPipeline",
    "EnhancedPipelineConfig",
    # State
    "PipelineState",
    "PipelineStage",
]
