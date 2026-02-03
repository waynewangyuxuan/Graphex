"""
Entity extraction agent.

Extracts entities (Concept, Event, Agent, Claim, Fact) from text chunks.
"""

import json
from typing import Any

from ..schema.nodes import Node, NodeType, NodeSource, NodeMetadata, Granularity
from .base import BaseAgent


class EntityExtractor(BaseAgent):
    """
    Extract entities from text chunks.

    Uses structured prompts to identify and classify knowledge units.
    """

    SYSTEM_PROMPT = """You are an expert Entity Extraction Agent for knowledge graph construction.

Your task is to extract all entities from the given text according to the schema.

## Entity Types

- **Concept**: Abstract concepts or categories (e.g., "democracy", "algorithm", "photosynthesis")
- **Event**: Things that happen with start/end time (e.g., "World War II", "product launch")
- **Agent**: Conscious actors - people, organizations (e.g., "Einstein", "Google", "the government")
- **Claim**: Propositions that can be true/false (e.g., "This policy is effective")
- **Fact**: Verified factual statements (e.g., "Water boils at 100°C")

## Guidelines

1. Extract ONLY entity types defined above
2. Use exact text spans from the source when possible
3. Assign confidence scores (0.0-1.0) based on how clearly the entity is defined
4. Each entity needs a clear label (2-10 words) and definition (1-3 sentences)
5. If an entity matches a known entity, note it in your response

## Output Format

Return a JSON object with an "entities" array:

```json
{
  "entities": [
    {
      "id": "entity_001",
      "type": "Concept",
      "label": "Short label",
      "definition": "Clear definition in 1-3 sentences.",
      "text_span": "exact text from source",
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
        **kwargs: Any,
    ) -> str:
        """
        Format input for entity extraction.

        Args:
            text: Chunk text to analyze
            document_id: Source document identifier
            known_entities: Previously extracted entities for deduplication
        """
        prompt_parts = []

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
