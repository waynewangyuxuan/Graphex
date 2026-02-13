"""
LLM-based extraction agents.

Agents:
- FirstPassAgent: Document understanding (Phase 1)
- EntityExtractor: Extract entities from text chunks (Phase 2)
- RelationExtractor: Identify relationships between entities
- GroundingVerifier: Verify entity grounding (Phase 3)
- Validator: Verify extraction quality
"""

from .base import BaseAgent, AgentResult
from .first_pass_agent import FirstPassAgent, DocumentUnderstanding
from .entity_extractor import EntityExtractor
from .relation_extractor import RelationExtractor
from .grounding_verifier import GroundingVerifier, VerificationResult
from .validator import Validator

__all__ = [
    "BaseAgent",
    "AgentResult",
    # Phase 1: Document Understanding
    "FirstPassAgent",
    "DocumentUnderstanding",
    # Phase 2: Extraction
    "EntityExtractor",
    "RelationExtractor",
    # Phase 3: Verification
    "GroundingVerifier",
    "VerificationResult",
    "Validator",
]
