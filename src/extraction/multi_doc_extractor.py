"""Multi-document narrative extraction.

Takes N single-document extraction results and builds cross-document relations.

Architecture:
  Doc A (tree + graph) ─┐
  Doc B (tree + graph) ──┼─→ Cross-Doc LLM → unified concept index + cross-relations
  Doc C (tree + graph) ─┘

The single-doc trees remain unchanged. This layer ADDS:
  1. Unified concept index (merge concepts across documents)
  2. Cross-document relations (how ideas in doc A relate to doc B)
  3. A meta-tree (high-level structure across all documents)
"""

import json
from typing import Optional

import litellm

from src.extraction.narrative_prompts import NARRATIVE_PROMPTS


# ── Cross-document prompt ────────────────────────────────────────────────

CROSS_DOC_PROMPT = """You are analyzing relationships BETWEEN multiple documents that have already been individually extracted into narrative graphs.

## Documents

{doc_summaries}

## Your task

### 1. Unified Concept Index
Identify concepts that appear across multiple documents. For each shared concept:
- Pick a canonical label
- List which documents use it and how

### 2. Cross-Document Relations
Find meaningful connections between segments in DIFFERENT documents. Types:
- **builds_on**: Doc B's idea extends or builds on Doc A's idea
- **contradicts**: The documents disagree or present opposing views
- **shares_mechanism**: Both use the same technique/approach
- **shares_problem**: Both address the same fundamental problem
- **generalizes**: One document's idea is a generalization of the other's
- **applies**: One document applies a concept introduced by the other

Only include MEANINGFUL connections — not trivial shared vocabulary.

### 3. Meta-Structure
Describe how the documents relate at a high level. What story do they tell together?

## Output: Return ONLY valid JSON, no markdown fences.
{
  "shared_concepts": [
    {
      "label": "Concept Name",
      "docs": [
        {"doc_id": "attention", "segment_ids": ["s3", "s7"], "role": "introduces"},
        {"doc_id": "bert", "segment_ids": ["s2"], "role": "builds_on"}
      ]
    }
  ],
  "cross_relations": [
    {
      "source_doc": "attention",
      "source_segment": "s5",
      "target_doc": "bert",
      "target_segment": "s3",
      "type": "builds_on",
      "annotation": "BERT uses the Transformer encoder architecture from Attention Is All You Need"
    }
  ],
  "meta_narrative": "One paragraph describing the overarching story across all documents."
}"""


# ── JSON helpers (shared) ────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    import re
    if not text:
        return {}
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {}


# ── Main pipeline ────────────────────────────────────────────────────────

def extract_multi_document(
    doc_results: dict[str, dict],
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Build cross-document relations from individual extraction results.

    Args:
        doc_results: dict mapping doc_id → extraction result (from extract_narrative)
        model: LLM model to use

    Returns:
        dict with shared_concepts, cross_relations, meta_narrative, tokens
    """
    # Build document summaries for prompt
    doc_summaries = []
    for doc_id, result in doc_results.items():
        schema = result.get("phase0", {}).get("schema", {})
        segments = result.get("segments", [])
        concept_index = result.get("concept_index", {})

        # Compact segment summary
        seg_lines = []
        for s in segments:
            seg_lines.append(f'  {s["id"]} [{s.get("type")}] "{s.get("title")}"')

        # Concept summary
        concepts = list(concept_index.keys())

        summary = f"""### Document: {doc_id}
Topic: {schema.get('topic', '?')}
Theme: {schema.get('theme', '?')}
Segments ({len(segments)}):
{chr(10).join(seg_lines[:20])}{'...' if len(seg_lines) > 20 else ''}
Concepts: {', '.join(concepts)}
"""
        doc_summaries.append(summary)

    all_summaries = "\n".join(doc_summaries)

    prompt = CROSS_DOC_PROMPT.replace("{doc_summaries}", all_summaries)

    # Call LLM
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please analyze cross-document relationships."},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    data = _parse_json(raw)
    tokens = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens,
    }

    return {
        "shared_concepts": data.get("shared_concepts", []),
        "cross_relations": data.get("cross_relations", []),
        "meta_narrative": data.get("meta_narrative", ""),
        "doc_ids": list(doc_results.keys()),
        "tokens": tokens,
    }
