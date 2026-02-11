"""
Main extraction pipeline.

Supports multiple LLM providers through LiteLLM.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..parsing.pdf_parser import PDFParser, ParsedDocument
from ..chunking.chunker import Chunker
from ..agents.entity_extractor import EntityExtractor
from ..agents.relation_extractor import RelationExtractor
from ..agents.validator import Validator
from ..agents.base import DEFAULT_MODEL
from ..schema.graph import KnowledgeGraph
from ..schema.nodes import Node, NodeSource
from ..schema.edges import Edge, EdgeSource
from ..context.entity_registry import EntityRegistry
from ..context.context_builder import ContextBuilder
from .state import PipelineState, PipelineStage


@dataclass
class PipelineConfig:
    """Pipeline configuration."""

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 75

    # LLM (LiteLLM format)
    # Examples:
    #   - "gemini/gemini-2.0-flash" (Google Gemini)
    #   - "claude-sonnet-4-20250514" (Anthropic Claude)
    #   - "gpt-4o" (OpenAI GPT-4)
    model: str = DEFAULT_MODEL
    max_tokens: int = 4096

    # Validation
    confidence_threshold: float = 0.7
    validate_with_llm: bool = False  # Use local validation for MVP


class Pipeline:
    """
    Knowledge extraction pipeline.

    Orchestrates the full workflow from document to knowledge graph.
    Uses LiteLLM for LLM calls, supporting multiple providers.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
    ) -> None:
        """
        Initialize pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.parser = PDFParser()
        self.chunker = Chunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        self.entity_extractor = EntityExtractor(
            model=self.config.model,
        )
        self.relation_extractor = RelationExtractor(
            model=self.config.model,
        )
        self.validator = Validator(
            model=self.config.model,
        )

    def run(self, input_path: Path) -> KnowledgeGraph:
        """
        Run the full extraction pipeline.

        Args:
            input_path: Path to input document (PDF or text)

        Returns:
            Extracted knowledge graph
        """
        state = PipelineState()

        try:
            # Stage 1: Parse
            state.advance_to(PipelineStage.PARSING)
            if input_path.suffix.lower() == ".pdf":
                doc = self.parser.parse(input_path)
            else:
                text = input_path.read_text()
                doc = self.parser.parse_text(text, input_path.stem)

            state.document_id = doc.document_id
            state.log(f"Parsed document: {doc.title} ({doc.page_count} pages)")

            # Stage 2: Chunk
            state.advance_to(PipelineStage.CHUNKING)
            state.chunks = self.chunker.chunk(doc.content, doc.document_id)
            state.log(f"Created {len(state.chunks)} chunks")

            # Stage 3: Extract
            state.advance_to(PipelineStage.EXTRACTING)
            context_builder = ContextBuilder(state.entity_registry)

            for i, chunk in enumerate(state.chunks):
                state.current_chunk_index = i
                state.log(f"Processing chunk {i + 1}/{len(state.chunks)}")

                # Extract entities
                entity_result = self.entity_extractor.execute(
                    text=chunk.text,
                    document_id=doc.document_id,
                    known_entities=state.entity_registry.all_entities()[:20],
                )

                if not entity_result.success:
                    state.add_warning(f"Entity extraction failed for chunk {i}")
                    continue

                entities: list[Node] = entity_result.output or []

                # Register entities and fix source
                for entity in entities:
                    entity.source = NodeSource(document_id=doc.document_id)
                    entity_id = state.entity_registry.register(entity)
                    chunk.extracted_entities.append(entity_id)
                    state.graph.add_node(entity)

                state.total_entities += len(entities)

                # Extract relations
                if entities:
                    relation_result = self.relation_extractor.execute(
                        text=chunk.text,
                        entities=entities,
                        document_id=doc.document_id,
                    )

                    if relation_result.success:
                        edges: list[Edge] = relation_result.output or []
                        for edge in edges:
                            edge.source = EdgeSource(document_id=doc.document_id)
                            try:
                                state.graph.add_edge(edge)
                                chunk.extracted_relations.append(edge.id)
                                state.total_relations += 1
                            except ValueError as e:
                                state.add_warning(f"Invalid edge: {e}")

                # Update context
                context_builder.add_chunk_result(chunk)
                state.chunks_processed += 1

            # Stage 4: Post-processing
            state.advance_to(PipelineStage.POST_PROCESSING)
            state.log("Validating extractions...")

            validation_result = self.validator.validate_locally(
                list(state.graph.nodes.values()),
                list(state.graph.edges.values()),
            )

            for issue in validation_result.issues:
                state.add_warning(f"{issue.item_id}: {issue.description}")

            # Stage 5: Build final graph
            state.advance_to(PipelineStage.BUILDING_GRAPH)
            state.graph.metadata.document_ids = [doc.document_id]

            state.advance_to(PipelineStage.COMPLETED)
            state.log(f"Completed: {state.graph.summary()}")

        except Exception as e:
            state.add_error(str(e))
            state.advance_to(PipelineStage.ERROR)
            raise

        return state.graph

    def run_text(self, text: str, document_id: str = "text") -> KnowledgeGraph:
        """
        Run extraction on raw text.

        Args:
            text: Text content to process
            document_id: Identifier for the document

        Returns:
            Extracted knowledge graph
        """
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            temp_path = Path(f.name)

        try:
            return self.run(temp_path)
        finally:
            temp_path.unlink()
