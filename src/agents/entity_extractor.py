"""
Entity extraction agent.

Extracts entities (Concept, Event, Agent, Claim, Fact) from text chunks.
Supports context from First-Pass analysis for guided extraction.
"""

import json
from typing import Any

from ..schema.nodes import Node, NodeType, NodeSource, NodeMetadata, Granularity
from .base import BaseAgent


class EntityExtractor(BaseAgent):
    """
    Extract entities from text chunks.

    Uses structured prompts to identify and classify knowledge units.
    Can be guided by First-Pass document understanding results.
    """

    SYSTEM_PROMPT = """You are an expert Entity Extraction Agent for knowledge graph construction.

Your task is to extract **teachable concepts** from the given text - concepts that the document is trying to teach the reader.

## Core Principle: Extract Knowledge, Not Mentions

Ask yourself: "Is the document TEACHING this concept, or just MENTIONING it?"

✅ **Extract** (document teaches this):
- Concepts that are defined: "X is..."
- Concepts that are explained: "X works by..."
- Concepts central to the document's purpose

❌ **Don't Extract** (document just mentions this):
- Filenames (main.c, test.py) - unless teaching file naming
- Author names - unless the document is ABOUT that person
- Code variable names - unless representing important concepts
- References to figures, pages, sections

## Entity Types

1. **Concept**: Abstract ideas the document explains
   - Example: "Condition Variable", "Bounded Buffer", "Mesa Semantics"

2. **Method**: Operations or procedures the document teaches
   - Example: "wait()", "signal()", "binary search"

3. **Event**: Historical events relevant to understanding
   - Example: "Renaissance", "Industrial Revolution"

4. **Agent**: People whose IDEAS are being taught (not just mentioned)
   - Example: "Dijkstra" (if teaching his contribution to the field)
   - ⚠️ NOT: document authors, reference authors

5. **Claim**: Rules or best practices the document advocates
   - Example: "Always use while loops with condition variables"

6. **Fact**: Verified statements the document presents as truth
   - Example: "π is irrational"

## Importance Levels

- **core**: Central to what the document teaches. Would appear in a summary.
- **supporting**: Helps understand core concepts. Background knowledge.
- **peripheral**: Briefly mentioned, not central to learning.

## Output Format

```json
{
  "entities": [
    {
      "id": "entity_001",
      "type": "Concept",
      "label": "Short label",
      "definition": "Clear definition in 1-3 sentences.",
      "importance": "core",
      "grounding_evidence": "The document says: 'X is defined as...'",
      "confidence": 0.95
    }
  ]
}
```"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        text: str,
        document_id: str,
        known_entities: list[Node] | None = None,
        concept_candidates: list[dict] | None = None,
        document_theme: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Format input for entity extraction.

        Args:
            text: Chunk text to analyze
            document_id: Source document identifier
            known_entities: Previously extracted entities for deduplication
            concept_candidates: Candidates from First-Pass analysis (Phase 1)
            document_theme: Document theme from First-Pass analysis
        """
        prompt_parts = []

        # Add First-Pass context if provided (Phase 1 results)
        if document_theme or concept_candidates:
            prompt_parts.append("## Document Context (from First-Pass Analysis)\n\n")

            if document_theme:
                prompt_parts.append(f"**Theme**: {document_theme}\n\n")

            if concept_candidates:
                prompt_parts.append("**Concepts this document is teaching**:\n")
                for candidate in concept_candidates[:15]:  # Limit to 15
                    name = candidate.get("name", "Unknown")
                    importance = candidate.get("importance", "supporting")
                    prompt_parts.append(f"- {name} ({importance})\n")
                prompt_parts.append("\n")
                prompt_parts.append(
                    "Focus on finding these concepts in the text. "
                    "If you find a concept NOT in this list, only extract it if "
                    "the document clearly defines/explains it.\n\n"
                )

        # Add known entities if provided
        if known_entities:
            known_list = [
                f"- {e.label} ({e.type.value}): {e.definition[:100]}..."
                for e in known_entities[:20]  # Limit to 20
            ]
            prompt_parts.append("## Known Entities (avoid duplicates)\n")
            prompt_parts.append("\n".join(known_list))
            prompt_parts.append("\n\n")

        # Add the text to analyze
        prompt_parts.append("## Text to Analyze\n\n")
        prompt_parts.append(text)
        prompt_parts.append(f"\n\n## Document ID: {document_id}")

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> list[Node]:
        """
        Parse LLM response into Node objects.

        Args:
            response: Raw LLM response text

        Returns:
            List of extracted Node objects
        """
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return []

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        entities = data.get("entities", [])
        nodes: list[Node] = []

        for entity in entities:
            try:
                node = Node(
                    id=entity.get("id", f"entity_{len(nodes):04d}"),
                    type=NodeType(entity.get("type", "Concept")),
                    label=entity.get("label", "Unknown"),
                    definition=entity.get("definition", "No definition provided"),
                    source=NodeSource(
                        document_id=entity.get("document_id", "unknown"),
                    ),
                    metadata=NodeMetadata(
                        granularity=Granularity.L2,
                        confidence=entity.get("confidence", 0.5),
                    ),
                )
                nodes.append(node)
            except Exception:
                continue  # Skip malformed entities

        return nodes
