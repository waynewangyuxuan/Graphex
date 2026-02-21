"""Prompts for the Progressive Understanding pipeline (ADR-0008).

Design principles:
- Each prompt is 300-600 tokens — enough for a complete logical chain, short enough
  to keep the model focused.
- No exhaustive rules or examples. The model gets clarity from the TASK FRAMING,
  not from a long checklist.
- Edge types are OPEN — the model creates descriptive relationship types that make
  sense for the content. No hardcoded list.
- Chunking is handled programmatically, not by the LLM.
- Placeholders use {curly_braces} and are filled via str.replace() at runtime.
"""

from .prompts import ENTITY_TYPES

# ── Shared schema reference (compact, reused across prompts) ────────────

_ENTITY_TYPES_COMPACT = ", ".join(ENTITY_TYPES)
# → "Concept, Method, Event, Agent, Claim, Fact"


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 0: SKIM
# ═══════════════════════════════════════════════════════════════════════════

SKIM_PROMPT = """You are reading a document to understand what it teaches, how it is structured, and what the reader should learn from it.

## Your task

Read the text below and produce a document schema. Think like a student skimming a chapter before studying it:
- What is this document about? (topic)
- What kind of document is this? (content_type)
- What is the one-sentence theme — the core idea the author wants the reader to understand?
- What is the key tension or tradeoff the document navigates?
- What is the learning arc — how does the argument or explanation progress?
- What are the major sections, and what does each one accomplish?
- What are the most important concepts the reader should watch for?

## Content types
research_paper, textbook_chapter, lecture_notes, technical_documentation, tutorial, survey_paper, blog_post, other

## Entity types for expected_core_entities
""" + _ENTITY_TYPES_COMPACT + """

## Output: Return ONLY valid JSON, no markdown fences.
{
  "topic": "string",
  "content_type": "string",
  "theme": "one-sentence theme",
  "narrative_root": {
    "summary": "2-4 sentence overview of what the document teaches and how",
    "key_tension": "the central tradeoff or problem being navigated",
    "learning_arc": "concise arc like: motivation → mechanism → application → rules"
  },
  "expected_core_entities": [
    {"label": "Name", "type": "Concept", "why": "brief reason"}
  ],
  "document_structure": [
    {"section": "Section Name", "purpose": "what this section accomplishes"}
  ]
}"""


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: CHUNK EXTRACTION (template — filled per chunk)
# ═══════════════════════════════════════════════════════════════════════════

CHUNK_EXTRACT_TEMPLATE = """You are building a knowledge graph by reading a document section by section. You have already read earlier sections and built up an understanding. Now process the next section.

## Document context
Topic: {topic}
Theme: {theme}
Learning arc: {learning_arc}

## Story so far
{narrative_so_far}

## Known entities (do NOT re-create these; reference them by ID when building relationships)
{entity_registry}

## Your task for this section

1. **Entities**: Extract new concepts this section teaches. Only create an entity if it is NOT already in the known entities list above. If the section refers to an existing entity, use its ID.
2. **Relationships**: Find relationships — both within this section AND connecting back to entities from earlier sections. This cross-section linking is critical. For each relationship, choose a short, reusable type label (1-2 words, CamelCase). Good: IsA, PartOf, Causes, Enables, Requires, Implements, Contrasts, Solves. Bad: IllustratesInefficiencyOf, CausedByIncorrectUseOf. Think of types as categories, not descriptions.
3. **Narrative**: Write 2-3 sentences summarizing what this section adds to the reader's understanding. Continue the story, don't repeat it.

Entity types: """ + _ENTITY_TYPES_COMPACT + """

Direction rule: SOURCE → TARGET means "source acts on / is part of / leads to target". The more specific, dependent, or acting entity is the source.

## Output: Return ONLY valid JSON, no markdown fences.
{
  "new_entities": [
    {"id": "{next_id}", "type": "Concept", "label": "Name", "definition": "1-2 sentences", "importance": "core"}
  ],
  "relationships": [
    {"source": "e1", "target": "e2", "type": "PartOf", "evidence": "brief quote", "importance": "core"}
  ],
  "narrative_update": "2-3 sentences continuing the story of what the reader now understands."
}"""


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: CONSOLIDATION
# ═══════════════════════════════════════════════════════════════════════════

CONSOLIDATION_PROMPT_TEMPLATE = """You have built a knowledge graph by processing a document section by section. Now review the complete graph for quality and coherence.

## Document context
Topic: {topic}
Theme: {theme}

## Complete entity list
{all_entities}

## Complete relationship list
{all_relationships}

## Full narrative
{full_narrative}

## Your task

Review the graph as a whole and fix problems:

1. **Duplicate entities**: If two entities refer to the same concept (e.g., "Bounded Buffer" and "Bounded Buffer Problem"), merge them. Return the ID to keep and the ID to remove.
2. **Missing critical relationships**: Now that you see the full picture, are there obvious relationships between entities from different sections that were missed? Add them. Use short, reusable type labels (1-2 words, CamelCase).
3. **Relationship corrections**: Are any edges using the wrong type or wrong direction? Fix them.
4. **Final narrative**: Write a cohesive 3-5 sentence summary of the entire document's knowledge structure.

## Output: Return ONLY valid JSON, no markdown fences.
{
  "entity_merges": [
    {"keep_id": "e1", "remove_id": "e5", "reason": "same concept"}
  ],
  "new_relationships": [
    {"source": "e1", "target": "e10", "type": "Enables", "evidence": "brief quote", "importance": "core"}
  ],
  "relationship_corrections": [
    {"original_source": "e3", "original_target": "e4", "original_type": "HasProperty", "corrected_source": "e4", "corrected_target": "e3", "corrected_type": "Enables", "reason": "direction was reversed"}
  ],
  "final_narrative": "3-5 sentence cohesive summary"
}"""


# ── Registry ────────────────────────────────────────────────────────────

PROGRESSIVE_PROMPTS = {
    "skim": SKIM_PROMPT,
    "chunk_extract": CHUNK_EXTRACT_TEMPLATE,
    "consolidation": CONSOLIDATION_PROMPT_TEMPLATE,
}
