# Entity Extraction from Documents — Knowledge Module

> Sources: KGGen (NeurIPS'25, Stanford), sift-kg, Graphiti (Zep), Microsoft GraphRAG
> Extracted: 2026-02-20

## The Core Mindset Problem

Our current approach: one LLM call per chunk, extracting entities + relationships simultaneously.
This is the **CocoIndex / iText2KG pattern** — fast, parallel-friendly, but has fundamental flaws.

The problem isn't just prompt tuning. It's an **architectural mindset** issue:

**Treating entity extraction like NER is wrong for knowledge graphs.**

Traditional NER: "find all mentions of things in this text"
KG extraction: "identify the concepts this text is ABOUT and how they relate"

These are fundamentally different tasks. Our current prompt does NER-style extraction ("find entities") when it should do **concept-level extraction** ("what is being taught/explained here").

## Three Architectural Insights from Open Source

### Insight 1: Two-Pass Extraction (KGGen, NeurIPS'25)

KGGen's core innovation: **separate entity extraction from relation extraction into two LLM calls**.

```
Pass 1: Extract entities (just names, no relationships)
Pass 2: Given entities + original text → extract relations
```

Why this works better than single-call:
- **Entities constrain relations**: Pass 2 uses `Literal[tuple(entities)]` as the type for subject/object. The LLM is FORCED to use only extracted entity names as relation endpoints. No hallucinated entities in relations.
- **Better focus per call**: Entity extraction call focuses entirely on "what things are discussed". Relation call focuses entirely on "how are they connected". Single-call forces the LLM to do both simultaneously, degrading both.
- **Fixup loop**: If Pass 2 produces relations with entities not in the list, a `FixedRelations` chain-of-thought corrects them.

Trade-off: 2x LLM calls per chunk. But total tokens are similar (relation call is constrained to known entities, so it's shorter).

### Insight 2: Document-Level Context Injection (sift-kg)

sift-kg's key innovation: **one extra LLM call per document** to generate a 2-3 sentence summary, then inject it into every chunk's extraction prompt.

```python
# One call per document (not per chunk)
doc_context = summarize_first_chunk(first_chunk_text)
# → "This is a textbook chapter about Condition Variables in OS threading..."

# Injected into every chunk's prompt:
"""
DOCUMENT CONTEXT (applies to entire document, not just this excerpt):
{doc_context}

TEXT:
{chunk_text}
"""
```

Why this matters: A chunk about `grep | wc` that says nothing about threading will still know the document is about threading. With context, the LLM can decide "grep and wc are peripheral to the document's topic" and skip them.

Cost: 1 extra LLM call per document (negligible — we have 92 chunks per doc).

### Insight 3: Entity-Only Output + Post-hoc Summary (Graphiti)

Graphiti separates extraction into multiple phases:
1. **Extract** entity names + types only (no definition, no description)
2. **Resolve** against existing graph (deduplication)
3. **Extract attributes/summary** as a SEPARATE step, AFTER resolution

Why: extracting definitions per-chunk creates the "definition pollution" problem we see (multiple "|"-concatenated definitions). By extracting summaries AFTER resolution, each entity gets ONE coherent summary synthesized from ALL its appearances.

## Pattern: The Optimal Extraction Architecture

Synthesizing all three insights:

```
Phase 0: Doc-level context (1 LLM call)
    first_chunk → "This document is about X, covering Y and Z"

Phase 1: Entity extraction (parallel, 1 call per chunk)
    chunk + doc_context → [entity_names] (just names + types, NO definitions)

Phase 2: Entity resolution (deterministic + LLM)
    all_entities → deduplicated_entities

Phase 3: Relation extraction (parallel, 1 call per chunk)
    chunk + doc_context + entity_list → [(subject, predicate, object)]
    subject/object CONSTRAINED to resolved entity names

Phase 4: Entity summary synthesis (1 call per entity, or batched)
    entity + all_chunks_mentioning_it → coherent_definition
```

Key properties:
- Phase 1 is embarrassingly parallel (our existing strength)
- Phase 2 uses Graphiti-style cascading ER (our next improvement)
- Phase 3 is parallel AND produces cleaner relations (entity-constrained)
- Phase 4 eliminates definition pollution

## Prompt Design Patterns

### Pattern A: Selectivity via Document Context
```
You are extracting key concepts from a chapter about {doc_context}.
Focus on concepts that are CENTRAL to the document's teaching goals.
Skip entities that are mentioned only as examples or analogies.
```

### Pattern B: Relationship Potential as Filter (KGGen)
```
Include only entities that are likely to have clear relationships
with other entities. An entity mentioned in isolation without
connections to the main narrative should be excluded.
```

### Pattern C: Constrained Relation Output (KGGen)
```python
# Dynamically create Pydantic model with entity literals
EntityLiteral = Literal[tuple(entities)]  # type constraint!
class RelationItem(BaseModel):
    subject: EntityLiteral  # MUST be from entity list
    predicate: str
    object: EntityLiteral   # MUST be from entity list
```

### Pattern D: Domain-Driven Schema (sift-kg)
```yaml
# domain.yaml — configurable per document type
entity_types:
  Concept:
    description: "Core idea or theory being taught"
    extraction_hints: ["typically introduced with a definition"]
  Method:
    description: "API, function, or technique"
    extraction_hints: ["typically shown in code examples"]
relation_types:
  PartOf: {source_types: [Method], target_types: [Concept]}
  Enables: {source_types: [Concept], target_types: [Concept]}
```

## What to Adopt for Graphex

### Must-haves (directly solve our problems):
1. **Document-level context injection** — kills peripheral noise (grep, wc, free(50))
2. **Two-pass extraction** — cleaner entities AND cleaner relations
3. **Entity-constrained relations** — no more orphaned relation endpoints

### Should-haves (improve quality significantly):
4. **Post-resolution summary synthesis** — eliminates definition pollution
5. **Domain-configurable entity types** — our schema (Concept, Method, Claim, etc.) as extraction guidance

### Nice-to-haves (optimize later):
6. **SemHash dedup** (KGGen) — deterministic pre-dedup before LLM
7. **KMeans clustering + intra-cluster LLM dedup** (KGGen) — scales to large entity sets
