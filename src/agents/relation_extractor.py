"""
Relation extraction agent.

Identifies relationships between entities.
"""

import json
from typing import Any

from ..schema.nodes import Node
from ..schema.edges import Edge, EdgeType, EdgeSource, ExtractionMethod
from .base import BaseAgent


class RelationExtractor(BaseAgent):
    """
    Extract relationships between entities.

    Takes entities and source text, identifies connections.
    """

    SYSTEM_PROMPT = """You are an expert Relation Extraction Agent for knowledge graph construction.

Your task is to identify relationships between the provided entities based on the source text.

## Relation Types

- **IsA**: Type attribution (e.g., "Dog IsA Mammal")
- **PartOf**: Part-whole relation (e.g., "Engine PartOf Car")
- **Causes**: Causation (e.g., "Rain Causes WetRoad")
- **Before**: Temporal ordering (e.g., "EventA Before EventB")
- **HasProperty**: Attribute (e.g., "Ice HasProperty Cold")
- **Supports**: Evidence supports claim (e.g., "Data Supports Hypothesis")
- **Attacks**: Contradicts or refutes (e.g., "CounterExample Attacks Theory")
- **RelatedTo**: Generic association (use only when no specific relation applies)

## Guidelines

1. Only create relations between entities in the provided list
2. Use the source text to justify each relation
3. Assign confidence based on how explicit the relation is in the text
4. Prefer specific relation types over RelatedTo
5. Include the evidence text span for each relation

## Output Format

Return a JSON object with a "relations" array:

```json
{
  "relations": [
    {
      "id": "rel_001",
      "source_id": "entity_001",
      "target_id": "entity_002",
      "type": "Causes",
      "confidence": 0.9,
      "evidence": "text span showing the relation"
    }
  ]
}
```"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        text: str,
        entities: list[Node],
        document_id: str,
        **kwargs: Any,
    ) -> str:
        """
        Format input for relation extraction.

        Args:
            text: Source text
            entities: Entities extracted from this text
            document_id: Source document identifier
        """
        prompt_parts = []

        # List entities
        prompt_parts.append("## Entities to Connect\n\n")
        for entity in entities:
            prompt_parts.append(
                f"- **{entity.id}** [{entity.type.value}]: {entity.label}\n"
                f"  Definition: {entity.definition}\n"
            )

        prompt_parts.append("\n## Source Text\n\n")
        prompt_parts.append(text)
        prompt_parts.append(f"\n\n## Document ID: {document_id}")

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> list[Edge]:
        """
        Parse LLM response into Edge objects.

        Args:
            response: Raw LLM response text

        Returns:
            List of extracted Edge objects
        """
        # Extract JSON from response
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return []

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        relations = data.get("relations", [])
        edges: list[Edge] = []

        for relation in relations:
            try:
                # Map string type to EdgeType enum
                edge_type_str = relation.get("type", "RelatedTo")
                try:
                    edge_type = EdgeType(edge_type_str)
                except ValueError:
                    edge_type = EdgeType.RELATED_TO

                edge = Edge(
                    id=relation.get("id", f"rel_{len(edges):04d}"),
                    source_id=relation.get("source_id", ""),
                    target_id=relation.get("target_id", ""),
                    type=edge_type,
                    confidence=relation.get("confidence", 0.5),
                    source=EdgeSource(
                        document_id=relation.get("document_id", "unknown"),
                        extraction_method=ExtractionMethod.EXPLICIT,
                    ),
                    annotation=relation.get("evidence"),
                )
                edges.append(edge)
            except Exception:
                continue  # Skip malformed relations

        return edges
