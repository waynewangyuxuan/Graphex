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

### CRITICAL: Dedup with existing segments
This section may OVERLAP with the previous section. Check the "Story so far" list carefully.
If the beginning of this section covers the SAME content as an existing segment, do NOT create a new segment for it. Instead, reference the existing segment ID in your relations. Only create segments for NEW content not already captured.

### Skip non-teaching content
Skip references, bibliographies, homework/exercise sections, and copyright notices. Only extract segments that teach something.

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
Preferred relation types (use these when they fit):
- **motivates**: A raises the need for B (typically problem → mechanism)
- **elaborates**: A provides more detail about B
- **exemplifies**: A is a concrete instance of B
- **enables**: A is a prerequisite that makes B possible
- **complicates**: A introduces a new problem for B
- **resolves**: A solves the problem raised by B
- **contrasts**: A and B are compared/contrasted
- **leads_to**: A flows into B in the argument (narrative sequence)

If none of these fit, you may use a different descriptive type, but strongly prefer the above list.

### Concept tags
For each segment, tag the key concepts it touches. Mark each as:
- **introduces**: This segment first introduces this concept
- **uses**: This segment references an already-known concept
- **deepens**: This segment adds new understanding to a known concept

Use consistent concept labels — check the "Story so far" for concept names already used and reuse them exactly.

### Anchor phrase (for text-graph binding)
For each segment, quote a SHORT phrase (8-15 words) copied EXACTLY from the section text that marks where this segment begins. This must be a verbatim substring of the input text — do not paraphrase.

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
      "anchor": "exact quote from the text (8-15 words)",
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
# REVIEW PASS: LLM-based final cleanup
# ═══════════════════════════════════════════════════════════════════════════

NARRATIVE_REVIEW_PROMPT = """You are reviewing a narrative structure graph extracted from a document. Your job is quality control — find and fix problems, don't add new content.

## Document context
Topic: {topic}
Theme: {theme}

## Current segment list
{all_segments}

## Current relation list
{all_relations}

## Current concept labels used
{concept_labels}

## Review tasks

### 1. Duplicate segments
Find segments that describe the SAME content (even if worded differently). These arise from chunk overlap during extraction.
For each duplicate pair, pick the one with a better summary to KEEP and mark the other for REMOVAL.

IMPORTANT: Only merge segments that are TRUE DUPLICATES — they cover the same content at a chunk boundary. Do NOT merge segments that discuss the same concept but at DIFFERENT POINTS in the narrative (e.g., a rule introduced early vs. the same rule reinforced later in a new context). Revisiting a concept in a new context is a valuable narrative pattern, not duplication.

### 2. Relation fixes
- Fix any relation where the type doesn't match the preferred list: motivates, elaborates, exemplifies, enables, complicates, resolves, contrasts, leads_to
- Remove relations that point to/from segments you're merging away
- Flag any relation that seems semantically wrong

### 3. Concept label normalization
If the same concept appears under different labels (e.g., "wait()" and "pthread_cond_wait" for the same thing, or "Lock" and "Mutex" when they mean the same thing in context), pick the most precise label and list the merges.

## Output: Return ONLY valid JSON, no markdown fences.
{
  "segment_merges": [
    {
      "keep_id": "s8",
      "remove_id": "s10",
      "reason": "Both describe the race condition from omitting locks"
    }
  ],
  "relation_fixes": [
    {
      "action": "change_type",
      "source": "s1",
      "target": "s2",
      "old_type": "explains",
      "new_type": "elaborates",
      "reason": "explains is not a preferred type"
    }
  ],
  "concept_merges": [
    {
      "keep_label": "pthread_cond_wait",
      "remove_label": "wait()",
      "reason": "Same function, use the precise POSIX name"
    }
  ]
}"""


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

NARRATIVE_PROMPTS = {
    "skim": NARRATIVE_SKIM_PROMPT,
    "chunk_extract": NARRATIVE_CHUNK_TEMPLATE,
    "review": NARRATIVE_REVIEW_PROMPT,
}
