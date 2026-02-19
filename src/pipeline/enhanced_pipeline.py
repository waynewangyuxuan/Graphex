"""
Enhanced extraction pipeline with four-phase approach.

Phase 1: First-Pass - Document understanding
Phase 2: Chunk Extraction - Guided by First-Pass results (with optional Gleaning)
Phase 3: Grounding Verification - Filter ungrounded entities
Phase 4: Entity Resolution - Merge duplicate entities via description aggregation

This pipeline addresses the core problem: LLM extracting "mentions" instead of "knowledge".
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import litellm

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

    # Gleaning (Phase 2 enhancement)
    max_gleanings: int = 1  # Adjustable; each round ~2x token cost for that chunk
    glean_chunk_token_threshold: int = 500  # Only glean chunks longer than this

    # Entity Resolution (Phase 4)
    enable_entity_resolution: bool = True

    # Validation
    confidence_threshold: float = 0.7


class EnhancedPipeline:
    """
    Four-phase knowledge extraction pipeline.

    Phase 1 (First-Pass): Understand what the document is trying to teach
    Phase 2 (Extraction): Extract entities guided by Phase 1 results + Gleaning
    Phase 3 (Verification): Filter out entities that aren't grounded
    Phase 4 (Resolution): Merge duplicate entities via description aggregation

    This approach solves the "filename extraction" problem by:
    1. First-Pass identifies "Condition Variable" as teachable, not "main.c"
    2. Extraction is guided to focus on teachable concepts
    3. Gleaning catches missed entities in dense chunks (max_gleanings rounds)
    4. Verification filters out anything without proper grounding
    5. Resolution merges cross-chunk duplicates and enriches descriptions
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

                # Gleaning: catch missed entities in long chunks
                approx_tokens = len(chunk.text) // 4
                if self.config.max_gleanings > 0 and approx_tokens > self.config.glean_chunk_token_threshold:
                    for glean_round in range(self.config.max_gleanings):
                        additional = self._run_gleaning(
                            chunk_text=chunk.text,
                            existing_entities=entities,
                            doc_id=doc.document_id,
                            concept_candidates=document_understanding.concept_candidates,
                            document_theme=document_understanding.theme,
                        )
                        if not additional:
                            break
                        state.log(
                            f"  Gleaning round {glean_round + 1}: +{len(additional)} entities"
                        )
                        entities.extend(additional)

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

            # ===== PHASE 4: Entity Resolution =====
            if self.config.enable_entity_resolution and len(state.graph.nodes) > 1:
                state.log("=== Phase 4: Entity Resolution ===")
                before_count = len(state.graph.nodes)
                self._run_entity_resolution(state.graph, state)
                after_count = len(state.graph.nodes)
                state.log(
                    f"Entity resolution: {before_count} → {after_count} nodes "
                    f"({before_count - after_count} merged)"
                )

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

    def _run_gleaning(
        self,
        chunk_text: str,
        existing_entities: list[Node],
        doc_id: str,
        concept_candidates: list[dict],
        document_theme: str,
    ) -> list[Node]:
        """
        Run one gleaning round: ask LLM for entities missed in the first pass.

        Shows the already-extracted entity list so the LLM focuses on NEW ones.

        Args:
            chunk_text: The chunk being processed
            existing_entities: Entities already extracted from this chunk
            doc_id: Document ID for source attribution
            concept_candidates: First-Pass concept candidates (for context)
            document_theme: Document theme (for context)

        Returns:
            Additional entities found (may be empty)
        """
        if not existing_entities:
            return []

        existing_labels = "\n".join(f"- {e.label}" for e in existing_entities)

        # Build context header matching what the entity extractor uses
        context_parts = []
        if document_theme:
            context_parts.append(f"**Theme**: {document_theme}\n")
        if concept_candidates:
            context_parts.append("**Concepts this document is teaching**:\n")
            for c in concept_candidates[:15]:
                context_parts.append(f"- {c.get('name', '')} ({c.get('importance', 'supporting')})\n")

        context_header = "".join(context_parts)

        user_prompt = (
            f"{context_header}\n"
            f"## Already extracted from this chunk:\n{existing_labels}\n\n"
            f"## Text to re-examine:\n\n{chunk_text}\n\n"
            f"## Document ID: {doc_id}\n\n"
            "Extract ONLY teachable entities NOT listed above. "
            "Use the same JSON format. Return an empty entities list if none were missed."
        )

        try:
            response = litellm.completion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.entity_extractor.get_system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.config.max_tokens,
            )
            response_text = response.choices[0].message.content
            return self.entity_extractor.parse_output(response_text)
        except Exception:
            return []

    def _run_entity_resolution(
        self,
        graph: KnowledgeGraph,
        state: PipelineState,
    ) -> None:
        """
        Phase 4: Merge duplicate entities using label + alias matching.

        Strategy: type-aware description aggregation (from KG_Pipeline_Patterns.md).
        Groups entities whose labels or aliases overlap, merges descriptions,
        takes majority type on conflict, and redirects edges to the canonical node.

        Args:
            graph: Knowledge graph to resolve in-place
            state: Pipeline state for logging
        """
        # Build label → canonical_id mapping
        label_to_canonical: dict[str, str] = {}
        groups: dict[str, list[Node]] = {}  # canonical_id → [nodes to merge into it]

        for node in list(graph.nodes.values()):
            match_keys = [node.label.lower()] + [a.lower() for a in node.aliases]

            # Find if any key already maps to a canonical
            canonical_id = None
            for key in match_keys:
                if key in label_to_canonical:
                    canonical_id = label_to_canonical[key]
                    break

            if canonical_id:
                groups[canonical_id].append(node)
            else:
                canonical_id = node.id
                groups[canonical_id] = [node]

            # Register all keys to this canonical (don't overwrite existing mappings)
            for key in match_keys:
                if key not in label_to_canonical:
                    label_to_canonical[key] = canonical_id

        # Merge groups with duplicates
        for canonical_id, group in groups.items():
            if len(group) <= 1:
                continue

            if canonical_id not in graph.nodes:
                continue

            canonical = graph.nodes[canonical_id]
            duplicates = [n for n in group[1:] if n.id != canonical_id and n.id in graph.nodes]

            if not duplicates:
                continue

            for dup in duplicates:
                # Merge description (concatenate if distinct)
                if dup.definition and dup.definition != canonical.definition:
                    # Truncate merged definition to stay within field max_length
                    merged = canonical.definition + " | " + dup.definition
                    canonical.definition = merged[:500]

                # Merge aliases
                new_aliases = list(set(canonical.aliases + dup.aliases + [dup.label]))
                canonical.aliases = new_aliases

                # Redirect edges: replace dup.id with canonical_id
                for edge in graph.edges.values():
                    if edge.source_id == dup.id:
                        edge.source_id = canonical_id
                    if edge.target_id == dup.id:
                        edge.target_id = canonical_id

                # Remove self-loops created by merging
                self_loops = [
                    eid for eid, e in graph.edges.items()
                    if e.source_id == e.target_id
                ]
                for eid in self_loops:
                    del graph.edges[eid]

                # Remove duplicate node
                del graph.nodes[dup.id]
                state.log(f"  Merged '{dup.label}' → '{canonical.label}'")

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
