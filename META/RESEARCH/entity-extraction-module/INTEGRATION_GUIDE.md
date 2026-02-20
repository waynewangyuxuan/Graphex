# Entity Extraction — Integration Guide for Graphex

## Current Problems Being Solved

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| Core entities missing (wait/signal/Lock/Mesa) | Single-call mixes entity+relation extraction, LLM under-extracts entities | Two-pass: entity-only first, then relations |
| Peripheral noise (grep/wc/free(50)) | No document-level context, chunk doesn't know "this doc is about CVs" | Doc-context injection |
| Definition pollution ("|" concatenation) | Definitions extracted per-chunk, naively merged | Post-resolution summary synthesis |
| Granularity inconsistency | No schema guidance on what granularity to extract | Domain config with entity types + hints |
| Type misassignment (Method vs Claim) | Free-form type selection per chunk | Constrained type IDs from schema |

## Implementation Plan

### Step 1: Add Document-Level Context (sift-kg pattern)

Before chunk extraction, generate a doc summary from the first chunk:

```python
def generate_doc_context(first_chunk_text: str, model: str) -> str:
    response = litellm.completion(
        model=model,
        messages=[{
            "role": "user",
            "content": (
                "Summarize this text excerpt in 2-3 sentences. "
                "Focus on: what type of document this is, "
                "what the main subject matter is, "
                "and what concepts are being taught.\n\n"
                f"TEXT:\n{first_chunk_text}"
            )
        }],
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()
```

Cost: 1 extra LLM call per document. Inject result into every chunk prompt.

### Step 2: Split into Two-Pass Extraction (KGGen pattern)

**Pass 1 — Entity extraction (parallel)**:
```python
ENTITY_EXTRACTION_PROMPT = """
DOCUMENT CONTEXT: {doc_context}

Extract key entities from this text. Return ONLY entity names and types.
Focus on concepts CENTRAL to the document's topic.
Skip entities mentioned only as examples or in passing.

ENTITY TYPES (use ONLY these):
- Concept: Core idea, theory, or abstraction being taught
- Method: API call, function, algorithm, or technique
- Claim: Rule, best practice, or recommendation
- Fact: Specific factual statement or data point
- Agent: Person, organization, or system
- Event: Named occurrence or historical development

TEXT: {chunk_text}

Return JSON: {"entities": [{"name": "...", "type": "..."}]}
"""
```

**Pass 2 — Relation extraction (parallel, after entity resolution)**:
```python
RELATION_EXTRACTION_PROMPT = """
DOCUMENT CONTEXT: {doc_context}

Extract relationships between the given ENTITIES from this text.
Subject and object MUST be from the ENTITIES list.

ENTITIES: {entity_names}

RELATION TYPES: IsA, PartOf, Causes, Before, HasProperty, Supports, Attacks, Enables, Contrasts

TEXT: {chunk_text}

Return JSON: {"relationships": [{"source": "...", "target": "...", "type": "...", "evidence": "..."}]}
"""
```

### Step 3: Entity-Constrained Relations

Use the KGGen pattern of dynamic Pydantic models:

```python
from pydantic import create_model
from typing import Literal

def create_relation_model(entity_names: list[str]):
    EntityLiteral = Literal[tuple(entity_names)]
    return create_model("Relation",
        source=(EntityLiteral, ...),
        target=(EntityLiteral, ...),
        type=(str, ...),
        evidence=(str, ...),
    )
```

### Step 4: Post-Resolution Summary Synthesis

After entity resolution, generate one coherent definition per entity:

```python
def synthesize_entity_summary(entity_name, entity_type, relevant_chunks):
    prompt = f"""
    Entity: {entity_name} (type: {entity_type})

    This entity appears in the following text passages:
    {format_chunks(relevant_chunks)}

    Write a concise definition (1-2 sentences) for this entity
    based on how it is used/explained in the passages above.
    """
    # One call per entity, or batch multiple entities
```

### Revised Pipeline Flow

```
PDF → Parse → Chunk
         ↓
    Doc Context (1 LLM call from first chunk)
         ↓
    Pass 1: Entity Extraction (parallel, all chunks)
         ↓
    Entity Resolution (Graphiti-style cascading)
         ↓
    Pass 2: Relation Extraction (parallel, entity-constrained)
         ↓
    Summary Synthesis (batched, post-resolution)
         ↓
    Knowledge Graph
```

### Files to Change

1. `benchmark/scripts/cocoindex_spike.py` — Restructure to two-pass
2. New: `src/extraction/doc_context.py` — Document context generator
3. New: `src/extraction/entity_extractor.py` — Pass 1 (entity-only)
4. New: `src/extraction/relation_extractor.py` — Pass 2 (entity-constrained)
5. New: `src/extraction/summary_synthesizer.py` — Post-resolution summaries

### Verification Checklist

- [ ] wait() and signal() extracted as separate entities (currently missing)
- [ ] Lock/Mutex extracted (currently missing)
- [ ] Mesa Semantics extracted (currently missing)
- [ ] grep, wc, free(50) NOT extracted (currently noise)
- [ ] Entity count per document: 15-25 range (not 78-113)
- [ ] No "|" concatenation in definitions
- [ ] Relations use ONLY entities from the resolved entity list
- [ ] Core node recall ≥ 95%
- [ ] Core edge recall ≥ 60%
- [ ] Total LLM calls: N_chunks * 2 + 1 (doc context) + ~3 (ER) + ~5 (summaries)

### Cost Analysis

Current: 92 chunks × 1 call = 92 LLM calls
Proposed: 1 (context) + 92 (entities) + 92 (relations) + ~3 (ER) + ~5 (summaries) = ~193 calls
~2x cost, but dramatically better quality. Entity extraction calls are SHORTER (no definitions), so token cost increase is less than 2x.

### Risk: Two-Pass May Over-Constrain Relations

KGGen's entity-literal typing means relations can ONLY reference extracted entities. If an important entity was missed in Pass 1, no relation can reference it. Mitigation: run Pass 1 with "be THOROUGH" guidance, accept slightly more entities (clean up in ER), rather than miss core ones.
