"""
Context management for cross-chunk consistency.

Provides:
- EntityRegistry: Track and deduplicate entities across chunks
- ContextBuilder: Construct extraction context with relevant info
"""

from .entity_registry import EntityRegistry
from .context_builder import ContextBuilder

__all__ = ["EntityRegistry", "ContextBuilder"]
