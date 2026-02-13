"""
Grounding Verifier Agent.

Phase 3 of the two-stage extraction pipeline.
Verifies that each extracted entity has proper grounding in the document,
filtering out entities that are merely "mentioned" vs "explained".
"""

import json
from dataclasses import dataclass
from typing import Any

from ..schema.nodes import Node
from .base import BaseAgent


@dataclass
class VerificationResult:
    """Result of grounding verification for a single entity."""

    entity_id: str
    is_grounded: bool
    grounding_type: str  # "defined", "explained", "exemplified", "merely_mentioned"
    evidence: str | None  # Text that grounds this entity
    confidence: float
    reasoning: str


class GroundingVerifier(BaseAgent):
    """
    Verifies that extracted entities have proper grounding in the source document.

    An entity is "grounded" if the document:
    1. Defines it ("X is ...")
    2. Explains it ("X works by ...")
    3. Uses it as a central example with explanation

    An entity is NOT grounded if:
    1. It's merely mentioned in passing
    2. It's a reference to external material
    3. It's metadata (author, filename, page number)
    """

    SYSTEM_PROMPT = """You are a Grounding Verification Agent. Your task is to verify whether extracted entities are actually "grounded" (defined/explained) in the source document.

## What is Grounding?

An entity is **grounded** if the document provides substantive information about it:
- **Defined**: "A condition variable IS an explicit queue that..."
- **Explained**: "The wait() operation WORKS BY releasing the lock and..."
- **Exemplified**: Detailed example showing how it works

An entity is **NOT grounded** if:
- **Merely mentioned**: "see main-two-cvs-if.c for code" (no explanation of what it is)
- **Referenced**: "as discussed by Lampson [1980]" (pointing to external source)
- **Metadata**: Author names, page numbers, figure numbers

## Grounding Types

1. **defined**: Document explicitly defines what this is
   - Evidence: "X is...", "X refers to...", "X means..."

2. **explained**: Document explains how it works or why it matters
   - Evidence: "X works by...", "X is important because...", "To use X, you..."

3. **exemplified**: Document provides detailed examples demonstrating it
   - Evidence: Extended code examples, walkthroughs, case studies

4. **merely_mentioned**: Only referenced, not explained
   - This means NOT GROUNDED

## Output Format

For each entity, return:

```json
{
  "verifications": [
    {
      "entity_id": "entity_001",
      "is_grounded": true,
      "grounding_type": "defined",
      "evidence": "A condition variable is an explicit queue that threads can put themselves on...",
      "confidence": 0.95,
      "reasoning": "The document provides a clear definition of what a condition variable is."
    },
    {
      "entity_id": "entity_002",
      "is_grounded": false,
      "grounding_type": "merely_mentioned",
      "evidence": null,
      "confidence": 0.9,
      "reasoning": "main-two-cvs-if.c is only mentioned as a filename for example code, not explained as a concept."
    }
  ]
}
```

## Guidelines

1. Be strict: "mentioned" is not the same as "grounded"
2. Look for definitional or explanatory language
3. Filenames, author names, and references are almost never grounded
4. If unsure, lean towards NOT grounded (precision over recall)
"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        entities: list[Node],
        document_text: str,
        **kwargs: Any,
    ) -> str:
        """
        Format input for grounding verification.

        Args:
            entities: Entities to verify
            document_text: Source document text
        """
        prompt_parts = []

        prompt_parts.append("## Entities to Verify\n\n")
        for entity in entities:
            prompt_parts.append(
                f"- **{entity.id}**: {entity.label}\n"
                f"  Type: {entity.type.value}\n"
                f"  Current definition: {entity.definition}\n\n"
            )

        prompt_parts.append("## Source Document\n\n")
        prompt_parts.append(document_text)
        prompt_parts.append("\n\n---\n\n")
        prompt_parts.append(
            "For each entity above, verify whether it is grounded (defined/explained) "
            "in the document, or merely mentioned."
        )

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> list[VerificationResult]:
        """
        Parse LLM response into verification results.

        Args:
            response: Raw LLM response text

        Returns:
            List of VerificationResult objects
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

        verifications = data.get("verifications", [])
        results: list[VerificationResult] = []

        for v in verifications:
            try:
                result = VerificationResult(
                    entity_id=v.get("entity_id", ""),
                    is_grounded=v.get("is_grounded", False),
                    grounding_type=v.get("grounding_type", "merely_mentioned"),
                    evidence=v.get("evidence"),
                    confidence=v.get("confidence", 0.5),
                    reasoning=v.get("reasoning", ""),
                )
                results.append(result)
            except Exception:
                continue

        return results

    def filter_grounded_entities(
        self,
        entities: list[Node],
        verification_results: list[VerificationResult],
        min_confidence: float = 0.6,
    ) -> list[Node]:
        """
        Filter entities to keep only grounded ones.

        Args:
            entities: Original entity list
            verification_results: Verification results
            min_confidence: Minimum confidence to trust the verification

        Returns:
            List of grounded entities
        """
        # Build lookup of verification results
        verifications = {v.entity_id: v for v in verification_results}

        grounded_entities = []
        for entity in entities:
            verification = verifications.get(entity.id)
            if verification is None:
                # No verification result - keep by default (conservative)
                grounded_entities.append(entity)
            elif verification.is_grounded and verification.confidence >= min_confidence:
                grounded_entities.append(entity)
            # else: not grounded or low confidence - filter out

        return grounded_entities
