"""
Enhanced extraction pipeline with three-phase approach.

Phase 1: First-Pass - Document understanding
Phase 2: Chunk Extraction - Guided by First-Pass results
Phase 3: Grounding Verification - Filter ungrounded entities

This pipeline addresses the core problem: LLM extracting "mentions" instead of "knowledge".
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..parsing.pdf_parser import PDFParser, ParsedDocument
from ..chunking.chunker import Chunker
from ..agents.first_pass_agent import FirstPassAgent, DocumentUnderstanding
from ..agents.entity_extractor import EntityExtractor
from ..agents.relation_extractor import RelationExtractor
from ..agents.grounding_verifier import GroundingVerifier
from ..agents.validator import Validator
from ..agents.base import DEFAULT_MODEL
from ..schema.graph import KnowledgeGraph
from ..schema.nodes import Node, NodeSource
from ..schema.edges import Edge, EdgeSource
from ..context.entity_registry import EntityRegistry
from ..context.context_builder import ContextBuilder
from .state import PipelineState, PipelineStage


@dataclass
class EnhancedPipelineConfig:
    """Enhanced pipeline configuration."""

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 75

    # LLM (LiteLLM format)
    model: str = DEFAULT_MODEL
    max_tokens: int = 4096

    # First-Pass
    first_pass_sample_size: int = 3000  # Characters to sample for First-Pass

    # Grounding Verification
    enable_grounding_verification: bool = True
    grounding_min_confidence: float = 0.6

    # Validation
    confidence_threshold: float = 0.7


class EnhancedPipeline:
    """
    Three-phase knowledge extraction pipeline.

    Phase 1 (First-Pass): Understand what the document is trying to teach
    Phase 2 (Extraction): Extract entities guided by Phase 1 results
    Phase 3 (Verification): Filter out entities that aren't grounded

    This approach solves the "filename extraction" problem by:
    1. First-Pass identifies "Condition Variable" as teachable, not "main.c"
    2. Extraction is guided to focus on teachable concepts
    3. Verification filters out anything without proper grounding
    """

    def __init__(
        self,
        config: Optional[EnhancedPipelineConfig] = None,
    ) -> None:
        """
        Initialize enhanced pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or EnhancedPipelineConfig()

        # Initialize components
        self.parser = PDFParser()
        self.chunker = Chunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        # Phase 1: First-Pass Agent
        self.first_pass_agent = FirstPassAgent(
            model=self.config.model,
        )

        # Phase 2: Extraction Agents
        self.entity_extractor = EntityExtractor(
            model=self.config.model,
        )
        self.relation_extractor = RelationExtractor(
            model=self.config.model,
        )

        # Phase 3: Verification Agents
        self.grounding_verifier = GroundingVerifier(
            model=self.config.model,
        )
        self.validator = Validator(
            model=self.config.model,
        )

    def run(self, input_path: Path) -> KnowledgeGraph:
        """
        Run the full three-phase extraction pipeline.

        Args:
            input_path: Path to input document (PDF or text)

        Returns:
            Extracted knowledge graph
        """
        state = PipelineState()

        try:
            # ===== Stage 1: Parse =====
            state.advance_to(PipelineStage.PARSING)
            if input_path.suffix.lower() == ".pdf":
                doc = self.parser.parse(input_path)
            else:
                text = input_path.read_text()
                doc = self.parser.parse_text(text, input_path.stem)

            state.document_id = doc.document_id
            state.log(f"Parsed document: {doc.title} ({doc.page_count} pages)")

            # ===== Stage 2: Chunk =====
            state.advance_to(PipelineStage.CHUNKING)
            state.chunks = self.chunker.chunk(doc.content, doc.document_id)
            state.log(f"Created {len(state.chunks)} chunks")

            # ===== PHASE 1: First-Pass Document Understanding =====
            state.log("=== Phase 1: First-Pass Document Understanding ===")
            document_understanding = self._run_first_pass(doc)
            state.log(f"Theme: {document_understanding.theme}")
            state.log(
                f"Identified {len(document_understanding.concept_candidates)} "
                "concept candidates"
            )

            # ===== PHASE 2: Guided Extraction =====
            state.advance_to(PipelineStage.EXTRACTING)
            state.log("=== Phase 2: Guided Chunk Extraction ===")
            context_builder = ContextBuilder(state.entity_registry)

            all_entities: list[Node] = []

            for i, chunk in enumerate(state.chunks):
                state.current_chunk_index = i
                state.log(f"Processing chunk {i + 1}/{len(state.chunks)}")

                # Extract entities WITH First-Pass guidance
                entity_result = self.entity_extractor.execute(
                    text=chunk.text,
                    document_id=doc.document_id,
                    known_entities=state.entity_registry.all_entities()[:20],
                    # NEW: Pass First-Pass context
                    concept_candidates=document_understanding.concept_candidates,
                    document_theme=document_understanding.theme,
                )

                if not entity_result.success:
                    state.add_warning(f"Entity extraction failed for chunk {i}")
                    continue

                entities: list[Node] = entity_result.output or []
                all_entities.extend(entities)

                # Register entities AND add to graph
                # (Must add to graph BEFORE relation extraction, because
                # add_edge() validates that source/target nodes exist)
                for entity in entities:
                    entity.source = NodeSource(document_id=doc.document_id)
                    entity_id = state.entity_registry.register(entity)
                    chunk.extracted_entities.append(entity_id)
                    # Add to graph immediately (may be filtered in Phase 3)
                    if entity.id not in state.graph.nodes:
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

                context_builder.add_chunk_result(chunk)
                state.chunks_processed += 1

            # ===== PHASE 3: Grounding Verification =====
            state.advance_to(PipelineStage.POST_PROCESSING)

            if self.config.enable_grounding_verification and all_entities:
                state.log("=== Phase 3: Grounding Verification ===")
                verified_entities = self._run_grounding_verification(
                    all_entities, doc.content, state
                )
                state.log(
                    f"Verified: {len(verified_entities)}/{len(all_entities)} "
                    "entities are grounded"
                )

                # Rebuild graph with only grounded entities
                verified_ids = {e.id for e in verified_entities}
                self._filter_graph(state.graph, verified_ids)
            else:
                verified_entities = all_entities

            # Add verified entities to graph
            for entity in verified_entities:
                if entity.id not in state.graph.nodes:
                    state.graph.add_node(entity)

            # Validation
            state.log("Validating extractions...")
            validation_result = self.validator.validate_locally(
                list(state.graph.nodes.values()),
                list(state.graph.edges.values()),
            )

            for issue in validation_result.issues:
                state.add_warning(f"{issue.item_id}: {issue.description}")

            # ===== Stage 5: Build final graph =====
            state.advance_to(PipelineStage.BUILDING_GRAPH)
            state.graph.metadata.document_ids = [doc.document_id]

            state.advance_to(PipelineStage.COMPLETED)
            state.log(f"Completed: {state.graph.summary()}")

        except Exception as e:
            state.add_error(str(e))
            state.advance_to(PipelineStage.ERROR)
            raise

        return state.graph

    def _run_first_pass(self, doc: ParsedDocument) -> DocumentUnderstanding:
        """
        Run Phase 1: First-Pass document understanding.

        Args:
            doc: Parsed document

        Returns:
            Document understanding with concept candidates
        """
        # Sample the document for First-Pass
        sample_size = self.config.first_pass_sample_size
        if len(doc.content) > sample_size:
            # Take beginning and end for better coverage
            half = sample_size // 2
            sample = doc.content[:half] + "\n...\n" + doc.content[-half:]
        else:
            sample = doc.content

        result = self.first_pass_agent.execute(
            document_text=sample,
            document_title=doc.title,
        )

        if result.success and result.output:
            return result.output

        # Fallback: empty understanding
        return DocumentUnderstanding(
            theme="Unknown",
            learning_objectives=[],
            concept_candidates=[],
        )

    def _run_grounding_verification(
        self,
        entities: list[Node],
        document_text: str,
        state: PipelineState,
    ) -> list[Node]:
        """
        Run Phase 3: Grounding verification.

        Args:
            entities: Entities to verify
            document_text: Full document text
            state: Pipeline state for logging

        Returns:
            List of grounded entities
        """
        # For long documents, sample the text
        max_text_len = 6000
        if len(document_text) > max_text_len:
            document_text = document_text[:max_text_len] + "\n...[truncated]..."

        result = self.grounding_verifier.execute(
            entities=entities,
            document_text=document_text,
        )

        if not result.success:
            state.add_warning("Grounding verification failed, keeping all entities")
            return entities

        verification_results = result.output or []

        # Filter to grounded entities
        grounded = self.grounding_verifier.filter_grounded_entities(
            entities,
            verification_results,
            min_confidence=self.config.grounding_min_confidence,
        )

        # Log what was filtered
        grounded_ids = {e.id for e in grounded}
        for entity in entities:
            if entity.id not in grounded_ids:
                state.log(f"  Filtered (not grounded): {entity.label}")

        return grounded

    def _filter_graph(
        self, graph: KnowledgeGraph, valid_entity_ids: set[str]
    ) -> None:
        """
        Filter graph to only include edges between valid entities.

        Args:
            graph: Knowledge graph to filter
            valid_entity_ids: Set of valid entity IDs
        """
        # Remove nodes not in valid set
        nodes_to_remove = [
            node_id
            for node_id in graph.nodes
            if node_id not in valid_entity_ids
        ]
        for node_id in nodes_to_remove:
            del graph.nodes[node_id]

        # Remove edges referencing invalid nodes
        edges_to_remove = [
            edge_id
            for edge_id, edge in graph.edges.items()
            if edge.source_id not in valid_entity_ids
            or edge.target_id not in valid_entity_ids
        ]
        for edge_id in edges_to_remove:
            del graph.edges[edge_id]

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
