"""
Recursive character text splitter with semantic boundary respect.

Parameters from Technical.md:
- chunk_size: 512 tokens
- chunk_overlap: 75 tokens (~15%)
- separators: paragraph > newline > sentence > space
"""

from dataclasses import dataclass, field
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkMetadata:
    """Metadata for a chunk."""

    document_id: str
    section_title: Optional[str] = None
    page_numbers: list[int] = field(default_factory=list)
    start_char: int = 0
    end_char: int = 0


@dataclass
class Chunk:
    """A chunk of text from a document."""

    id: str
    index: int
    text: str
    metadata: ChunkMetadata
    extracted_entities: list[str] = field(default_factory=list)
    extracted_relations: list[str] = field(default_factory=list)


class Chunker:
    """
    Split documents into chunks with semantic boundary respect.

    Uses recursive character splitting with configurable separators.
    """

    # Default separators in priority order
    DEFAULT_SEPARATORS = [
        "\n\n",  # Paragraph
        "\n",  # Newline
        "。",  # Chinese period
        ". ",  # English period
        " ",  # Space
        "",  # Character (fallback)
    ]

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 75,
        separators: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters (approx tokens)
            chunk_overlap: Overlap between chunks
            separators: Custom separators in priority order
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk(self, text: str, document_id: str) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text: Document text to split
            document_id: Identifier for source document

        Returns:
            List of Chunk objects
        """
        # Use langchain splitter
        docs = self._splitter.create_documents([text])

        chunks: list[Chunk] = []
        current_pos = 0

        for i, doc in enumerate(docs):
            chunk_text = doc.page_content

            # Find position in original text
            start = text.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_text)

            chunk = Chunk(
                id=f"{document_id}_chunk_{i:04d}",
                index=i,
                text=chunk_text,
                metadata=ChunkMetadata(
                    document_id=document_id,
                    start_char=start,
                    end_char=end,
                ),
            )
            chunks.append(chunk)

            # Move position forward (accounting for overlap)
            current_pos = max(start + 1, end - self.chunk_overlap)

        return chunks

    def chunk_with_context(
        self, text: str, document_id: str, context_size: int = 100
    ) -> list[Chunk]:
        """
        Split text into chunks with extended context for each chunk.

        Useful for providing surrounding context to extraction agents.

        Args:
            text: Document text to split
            document_id: Identifier for source document
            context_size: Characters of context to include before/after

        Returns:
            List of Chunk objects with extended text
        """
        base_chunks = self.chunk(text, document_id)

        for chunk in base_chunks:
            start = max(0, chunk.metadata.start_char - context_size)
            end = min(len(text), chunk.metadata.end_char + context_size)
            chunk.text = text[start:end]
            chunk.metadata.start_char = start
            chunk.metadata.end_char = end

        return base_chunks
