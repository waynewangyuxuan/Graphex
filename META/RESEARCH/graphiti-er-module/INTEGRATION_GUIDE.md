# Graphiti ER Pattern — Integration Guide for Graphex

## Current Problem

Our entity resolution (iText2KG pattern: embedding cosine similarity θ=0.6-0.8) produces:
- **Under-merge**: 78 entities vs target ~20 (most duplicates not caught)
- **Over-merge**: Core entities lost ("lock/mutex", "use while loop rule")
- **Root cause**: Embedding similarity is unreliable for short entity names

## Proposed Change: Replace ER with Graphiti-Style Three-Layer Cascade

### Implementation Plan

#### Step 1: Replace EntityResolver with Cascading Resolver

```python
class CascadingResolver:
    """Graphiti-style three-layer entity resolution."""

    # Tunable constants
    ENTROPY_THRESHOLD = 1.5
    MIN_NAME_LENGTH = 6
    JACCARD_THRESHOLD = 0.9

    def resolve(self, new_entities, existing_entities):
        """
        Returns: (resolved_entities, uuid_map)
        Layer 1: exact normalized match
        Layer 2: entropy-gated 3-gram Jaccard
        Layer 3: LLM batch dedup (unresolved only)
        """
```

#### Step 2: Add Entropy Gate

This is the critical fix for our over-merge problem:

```python
def _has_high_entropy(name: str) -> bool:
    """Short/repetitive names → skip fuzzy, send to LLM."""
    normalized = normalize(name)
    if len(normalized) < 6 and len(normalized.split()) < 2:
        return False
    entropy = shannon_entropy(normalized)
    return entropy >= 1.5
```

Entities like "Lock", "Mutex", "Thread", "API" will bypass fuzzy matching entirely.

#### Step 3: Replace Embedding Similarity with Character Jaccard

```python
def _shingle_jaccard(name_a: str, name_b: str) -> float:
    """3-gram character Jaccard similarity."""
    shingles_a = {name_a[i:i+3] for i in range(len(name_a)-2)}
    shingles_b = {name_b[i:i+3] for i in range(len(name_b)-2)}
    intersection = len(shingles_a & shingles_b)
    union = len(shingles_a | shingles_b)
    return intersection / union if union else 0.0
```

At our scale (~100 entities per document), brute-force pairwise Jaccard is fast enough. Skip MinHash/LSH unless we hit performance issues.

#### Step 4: Add LLM Batch Dedup as Layer 3

```python
async def _llm_batch_dedup(unresolved, existing, chunk_context):
    """One LLM call to resolve all ambiguous entities."""
    prompt = f"""
    ENTITIES (extracted, need resolution):
    {format_entities(unresolved)}

    EXISTING ENTITIES (already resolved):
    {format_entities(existing)}

    For each ENTITY, determine if it duplicates an EXISTING ENTITY.
    Only mark as duplicates if they refer to the SAME concept.
    Return: {{id, best_name, duplicate_name_or_empty}}
    """
    # Single LLM call, not N² pairwise
```

### Parallel Pipeline Integration

Our pipeline (parallel extraction → post-hoc resolution):

```
Phase 1: Parallel Extraction (existing, no change)
    ThreadPool → [chunk_1_entities, chunk_2_entities, ..., chunk_N_entities]

Phase 2: Sequential Resolution (new)
    entity_registry = {}
    for chunk_entities in all_chunk_results:
        resolved = cascading_resolve(chunk_entities, entity_registry)
        entity_registry.update(resolved)
```

Note: Phase 2 is sequential because each chunk's resolution depends on the growing registry. But Phase 1 (the expensive part — LLM extraction) is fully parallel. Phase 2 is fast (mostly exact + Jaccard, occasionally one LLM call).

Alternative: resolve all entities at once in a single pass:
```
all_entities = flatten(all_chunk_results)
deduplicated = cascading_resolve_all(all_entities)
```
This is simpler but may send more to LLM. Try this first.

### Files to Change

1. **`src/resolution/entity_resolver.py`** — Replace embedding-based resolver with cascading resolver
2. **`src/resolution/parallel_merge.py`** — May simplify; binary tree merge may no longer be needed
3. **`benchmark/scripts/cocoindex_spike.py`** — Update `merge_chunk_results()` to use new resolver

### Verification Checklist

- [ ] "Lock" and "Mutex" resolve correctly (should NOT be auto-merged by fuzzy, only by LLM if appropriate)
- [ ] "Condition Variable" and "condition variable" merge (exact match after normalization)
- [ ] "Bounded Buffer Problem" and "Bounded Buffer" merge (Jaccard ≥ 0.9 on high-entropy names)
- [ ] Short names like "Lock", "API", "Thread" → entropy gate → LLM path
- [ ] Entity count reduces from ~78-113 to ~15-25 range
- [ ] Core node recall ≥ 95% (was 100% before ER, 75% with current ER)
- [ ] Core edge recall ≥ 50% (was 50% before ER, 25% with current ER)
- [ ] Total LLM calls for ER ≤ 3 per document (batch dedup, not pairwise)

### Dependencies

- No new dependencies for Layers 1-2 (pure Python string operations)
- Layer 3 reuses existing `litellm` for LLM calls
- Can remove `sentence-transformers` dependency if embedding-based ER fully replaced

### Risk Assessment

- **Low risk**: Layers 1-2 are deterministic, well-tested pattern from production system (20k+ stars)
- **Medium risk**: Layer 3 LLM prompt needs tuning for educational content (Graphiti's prompt is optimized for conversational/agent memory)
- **Mitigation**: Start with Layers 1-2 only, add Layer 3 incrementally
