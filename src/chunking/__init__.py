"""
Document chunking module.

Splits documents into chunks respecting semantic boundaries.
"""

from .chunker import Chunker, Chunk

__all__ = ["Chunker", "Chunk"]
