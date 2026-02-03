"""
Validation agent.

Verifies extraction quality and flags issues.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from ..schema.nodes import Node
from ..schema.edges import Edge
from .base import BaseAgent


@dataclass
class ValidationIssue:
    """An issue found during validation."""

    item_id: str
    item_type: str  # "node" or "edge"
    issue_type: str
    description: str
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """Result of validation."""

    validated_nodes: list[Node] = field(default_factory=list)
    validated_edges: list[Edge] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    needs_review: list[str] = field(default_factory=list)


class Validator(BaseAgent):
    """
    Validate extracted entities and relations.

    Checks for:
    - Schema consistency
    - Evidence verification
    - Type constraints
    - Confidence thresholds
    """

    CONFIDENCE_THRESHOLD = 0.7

    SYSTEM_PROMPT = """You are a Quality Assurance Agent for knowledge graph extraction.

Your task is to validate extracted entities and relations against the source text.

## Validation Rules

1. **Schema Consistency**: Types must be valid (Concept, Event, Agent, Claim, Fact for nodes; IsA, PartOf, Causes, Before, HasProperty, Supports, Attacks, RelatedTo for edges)
2. **Evidence Verification**: Entities should be grounded in the source text
3. **Type Constraints**: Relations should connect appropriate entity types
4. **Definition Quality**: Definitions should be clear and accurate
5. **Duplicate Detection**: Flag potential duplicates

## Output Format

Return a JSON object:

```json
{
  "valid_entities": ["entity_001", "entity_002"],
  "valid_relations": ["rel_001"],
  "issues": [
    {
      "item_id": "entity_003",
      "item_type": "node",
      "issue_type": "weak_evidence",
      "description": "Entity not clearly mentioned in source text",
      "severity": "warning"
    }
  ],
  "needs_review": ["entity_004"]
}
```"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        text: str,
        nodes: list[Node],
        edges: list[Edge],
        **kwargs: Any,
    ) -> str:
        """
        Format input for validation.

        Args:
            text: Source text
            nodes: Extracted nodes to validate
            edges: Extracted edges to validate
        """
        prompt_parts = []

        # Entities
        prompt_parts.append("## Entities to Validate\n\n")
        for node in nodes:
            prompt_parts.append(
                f"- **{node.id}** [{node.type.value}]: {node.label}\n"
                f"  Definition: {node.definition}\n"
                f"  Confidence: {node.metadata.confidence}\n"
            )

        # Relations
        prompt_parts.append("\n## Relations to Validate\n\n")
        for edge in edges:
            prompt_parts.append(
                f"- **{edge.id}** [{edge.type.value}]: {edge.source_id} → {edge.target_id}\n"
                f"  Confidence: {edge.confidence}\n"
            )

        # Source text
        prompt_parts.append("\n## Source Text\n\n")
        prompt_parts.append(text)

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> ValidationResult:
        """
        Parse LLM response into ValidationResult.

        Args:
            response: Raw LLM response text

        Returns:
            ValidationResult with validated items and issues
        """
        result = ValidationResult()

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return result

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return result

        # Parse issues
        for issue_data in data.get("issues", []):
            try:
                issue = ValidationIssue(
                    item_id=issue_data.get("item_id", ""),
                    item_type=issue_data.get("item_type", "node"),
                    issue_type=issue_data.get("issue_type", "unknown"),
                    description=issue_data.get("description", ""),
                    severity=issue_data.get("severity", "warning"),
                )
                result.issues.append(issue)
            except Exception:
                continue

        result.needs_review = data.get("needs_review", [])

        return result

    def validate_locally(
        self, nodes: list[Node], edges: list[Edge]
    ) -> ValidationResult:
        """
        Perform local validation without LLM.

        Checks confidence thresholds and basic constraints.

        Args:
            nodes: Nodes to validate
            edges: Edges to validate

        Returns:
            ValidationResult
        """
        result = ValidationResult()
        node_ids = {n.id for n in nodes}

        # Validate nodes
        for node in nodes:
            if (node.metadata.confidence or 0) < self.CONFIDENCE_THRESHOLD:
                result.needs_review.append(node.id)
                result.issues.append(
                    ValidationIssue(
                        item_id=node.id,
                        item_type="node",
                        issue_type="low_confidence",
                        description=f"Confidence {node.metadata.confidence} below threshold",
                        severity="warning",
                    )
                )
            else:
                result.validated_nodes.append(node)

        # Validate edges
        for edge in edges:
            issues = []

            # Check endpoints exist
            if edge.source_id not in node_ids:
                issues.append(f"Source node {edge.source_id} not found")
            if edge.target_id not in node_ids:
                issues.append(f"Target node {edge.target_id} not found")

            # Check confidence
            if (edge.confidence or 0) < self.CONFIDENCE_THRESHOLD:
                result.needs_review.append(edge.id)
                issues.append(f"Low confidence: {edge.confidence}")

            if issues:
                result.issues.append(
                    ValidationIssue(
                        item_id=edge.id,
                        item_type="edge",
                        issue_type="validation_failed",
                        description="; ".join(issues),
                        severity="error" if edge.source_id not in node_ids else "warning",
                    )
                )
            else:
                result.validated_edges.append(edge)

        return result
