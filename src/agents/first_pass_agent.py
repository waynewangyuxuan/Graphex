"""
First-Pass Agent for document understanding.

Phase 1 of the two-stage extraction pipeline.
Analyzes the document to identify what concepts it is trying to teach,
before any chunk-level extraction happens.
"""

import json
from dataclasses import dataclass
from typing import Any

from .base import BaseAgent


@dataclass
class DocumentUnderstanding:
    """Output from first-pass document analysis."""

    theme: str  # What is this document about?
    learning_objectives: list[str]  # What should the reader learn?
    concept_candidates: list[dict]  # Concepts the document is teaching
    # Each candidate: {"name": str, "importance": "core"|"supporting", "why": str}


class FirstPassAgent(BaseAgent):
    """
    First-pass agent for document understanding.

    This agent reads the document (or a representative sample) and identifies:
    1. The document's main theme/topic
    2. What the document is trying to teach the reader
    3. Candidate concepts that should be extracted

    This provides context for the subsequent chunk-level extraction,
    helping filter out noise (like filenames, author names) that are
    not part of what the document is teaching.
    """

    SYSTEM_PROMPT = """You are a Document Understanding Agent. Your task is to analyze a document and identify what knowledge it is trying to convey.

## Your Goal

Imagine a student reads this document. After reading, what concepts should they have learned?
Your job is to identify these "teachable concepts" - the knowledge the document is explicitly trying to convey.

## Key Distinction

**Teachable Concepts** (EXTRACT these):
- Concepts the document defines or explains
- Ideas the document wants the reader to understand
- Terms that are central to the document's purpose

**Incidental Mentions** (DO NOT include):
- Author names (unless the document is ABOUT that person)
- Filenames, code variable names (unless the document is teaching naming conventions)
- References to other works (unless comparing/contrasting ideas)
- Page numbers, figure numbers, section markers

## Example

For a document about "Condition Variables in Operating Systems":

✅ Teachable Concepts:
- Condition Variable (the document explains what it is)
- wait() operation (the document teaches how it works)
- signal() operation (the document teaches how it works)
- Producer-Consumer Problem (the document uses this as an example to teach)
- Mesa Semantics (the document explains this concept)

❌ Incidental Mentions:
- "main-two-cvs-if.c" (just a filename for example code)
- "ARPACI-DUSSEAU" (author, not what the document teaches)
- "Figure 30.1" (just a reference marker)

## Output Format

Return a JSON object:

```json
{
  "theme": "A one-sentence description of what this document is about",
  "learning_objectives": [
    "After reading, the reader should understand X",
    "After reading, the reader should be able to Y"
  ],
  "concept_candidates": [
    {
      "name": "Concept Name",
      "importance": "core",
      "why": "The document dedicates significant space to explaining this"
    },
    {
      "name": "Another Concept",
      "importance": "supporting",
      "why": "Mentioned to help understand a core concept"
    }
  ]
}
```

## Importance Levels

- **core**: Document's main teaching points. Would appear in a summary.
- **supporting**: Helps explain core concepts. Background knowledge.
"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        document_text: str,
        document_title: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Format input for first-pass analysis.

        Args:
            document_text: Full document text or representative sample
            document_title: Optional document title for context
        """
        prompt_parts = []

        if document_title:
            prompt_parts.append(f"## Document Title: {document_title}\n\n")

        prompt_parts.append("## Document Content\n\n")
        prompt_parts.append(document_text)
        prompt_parts.append("\n\n---\n\n")
        prompt_parts.append("Analyze this document and identify the teachable concepts.")

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> DocumentUnderstanding:
        """
        Parse LLM response into DocumentUnderstanding.

        Args:
            response: Raw LLM response text

        Returns:
            DocumentUnderstanding with extracted analysis
        """
        # Extract JSON from response
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return self._empty_result()

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return self._empty_result()

        return DocumentUnderstanding(
            theme=data.get("theme", "Unknown"),
            learning_objectives=data.get("learning_objectives", []),
            concept_candidates=data.get("concept_candidates", []),
        )

    def _empty_result(self) -> DocumentUnderstanding:
        """Return empty result on parse failure."""
        return DocumentUnderstanding(
            theme="Parse error",
            learning_objectives=[],
            concept_candidates=[],
        )
