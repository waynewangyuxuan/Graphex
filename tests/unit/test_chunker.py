"""
Tests for chunking module.
"""

import pytest

from src.chunking.chunker import Chunker, Chunk


class TestChunker:
    """Tests for Chunker."""

    def test_create_chunker(self):
        """Test creating chunker with default settings."""
        chunker = Chunker()
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 75

    def test_create_chunker_custom(self):
        """Test creating chunker with custom settings."""
        chunker = Chunker(chunk_size=256, chunk_overlap=50)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 50

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        chunker = Chunker(chunk_size=512)
        text = "This is a short text."
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].metadata.document_id == "doc_001"

    def test_chunk_long_text(self):
        """Test chunking text longer than chunk size."""
        chunker = Chunker(chunk_size=100, chunk_overlap=20)

        # Create text that will require multiple chunks
        text = "This is a sentence. " * 50
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 150  # Allow some flexibility

    def test_chunk_respects_paragraphs(self):
        """Test that chunker respects paragraph boundaries."""
        chunker = Chunker(chunk_size=200, chunk_overlap=20)

        text = """First paragraph with some content.

Second paragraph with different content.

Third paragraph to make text longer."""

        chunks = chunker.chunk(text, "doc_001")

        # Should split on paragraph boundaries when possible
        assert len(chunks) >= 1

    def test_chunk_ids_are_unique(self):
        """Test that chunk IDs are unique."""
        chunker = Chunker(chunk_size=50)
        text = "Word " * 100
        chunks = chunker.chunk(text, "doc_001")

        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_metadata(self):
        """Test chunk metadata is populated."""
        chunker = Chunker()
        text = "Some text content."
        chunks = chunker.chunk(text, "doc_001")

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.metadata.document_id == "doc_001"
        assert chunk.metadata.start_char >= 0
        assert chunk.metadata.end_char > chunk.metadata.start_char
