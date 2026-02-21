"""Prompts for Narrative Structure extraction.

Design principles:
- Extract NARRATIVE STRUCTURE, not entities and relationships.
- Nodes are segments (what the author is saying), not concepts.
- Edges are discourse relations (how segments connect rhetorically).
- Concepts are lightweight tags on segments, not first-class entities.
- Two-phase: Phase 0 (Skim) → Programmatic Chunking → Phase 1 (Sequential).
- No Phase 2 consolidation needed — segments don't suffer from entity dedup.
"""


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 0: SKIM — same as before, produces document schema
# ═══════════════════════════════════════════════════════════════════════════

NARRATIVE_SKIM_PROMPT = """You are reading a document to understand its teaching structure — how the author guides the reader from ignorance to understanding.

## Your task

Read the text below and answer:
- What is this document about? (topic)
- What is the one-sentence theme — the core idea the author wants the reader to understand?
- What is the key tension or tradeoff the document navigates?
- What is the learning arc — the path from "not knowing" to "understanding"?
- What are the major concepts the reader should watch for?

## Output: Return ONLY valid JSON, no markdown fences.
{
  "topic": "string",
  "theme": "one-sentence core idea",
  "key_tension": "the central problem or tradeoff",
  "learning_arc": "step-by-step arc, e.g.: motivation → mechanism → pitfall → rule",
  "key_concepts": ["Concept A", "Concept B", "..."],
  "content_type": "textbook_chapter | research_paper | tutorial | lecture_notes | other"
}"""


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: CHUNK NARRATIVE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

NARRATIVE_CHUNK_TEMPLATE = """You are analyzing a document's narrative structure — how the author teaches the reader step by step.

## Document context
Topic: {topic}
Theme: {theme}
Learning arc: {learning_arc}

## Story so far
{segments_so_far}

## Your task for this section

Read the section below and extract its NARRATIVE SEGMENTS — the rhetorical building blocks of the author's argument.

A segment is a coherent unit of the author's teaching: a problem statement, a mechanism explanation, an example, a rule, etc. Most sections contain 2-5 segments.

### Segment types
- **setup**: Sets context, introduces background, establishes prerequisites
- **problem**: Raises a problem, reveals a difficulty, shows why something is needed
- **mechanism**: Explains how something works — a concept, algorithm, API, technique
- **example**: Concrete code, scenario, figure, or illustration
- **rule**: Best practice, design rule, guideline, "always do X"
- **consequence**: Result, implication, what happens if you do/don't do something
- **contrast**: Compares two approaches, semantics, or designs
- **summary**: Wraps up, reviews key points

### Discourse relations (connect segments)
- **motivates**: A raises the need for B (typically problem → mechanism)
- **elaborates**: A provides more detail about B
- **exemplifies**: A is a concrete instance of B
- **enables**: A is a prerequisite that makes B possible
- **complicates**: A introduces a new problem for B
- **resolves**: A solves the problem raised by B
- **contrasts**: A and B are compared/contrasted
- **leads_to**: A flows into B in the argument (narrative sequence)

### Concept tags
For each segment, tag the key concepts it touches. Mark each as:
- **introduces**: This segment first introduces this concept
- **uses**: This segment references an already-known concept
- **deepens**: This segment adds new understanding to a known concept

### Connecting to earlier segments
CRITICAL: When a new segment relates to a segment from an earlier section, create a cross-section relation. This is how the narrative graph becomes connected.

## Output: Return ONLY valid JSON, no markdown fences.
{
  "segments": [
    {
      "id": "{next_id}",
      "type": "mechanism",
      "title": "short title (5-10 words)",
      "content": "2-4 sentence summary of what this segment teaches",
      "concepts": [
        {"label": "Concept Name", "role": "introduces"}
      ],
      "importance": "core"
    }
  ],
  "relations": [
    {
      "source": "s1",
      "target": "s2",
      "type": "motivates",
      "annotation": "brief explanation"
    }
  ]
}"""


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

NARRATIVE_PROMPTS = {
    "skim": NARRATIVE_SKIM_PROMPT,
    "chunk_extract": NARRATIVE_CHUNK_TEMPLATE,
}
