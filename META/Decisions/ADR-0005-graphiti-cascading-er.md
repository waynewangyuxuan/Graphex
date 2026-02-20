# ADR-0005: Graphiti-Style Cascading Entity Resolution

- **Status**: Accepted
- **Date**: 2026-02-20
- **Deciders**: Wayne Wang
- **Supersedes**: [ADR-0004](ADR-0004-embedding-entity-resolution.md)

## Context

ADR-0004 adopted embedding cosine similarity (iText2KG pattern) for entity resolution.
Benchmark results revealed a fundamental problem:

- θ=0.8: 113→78 entities (under-merge, many duplicates remain)
- θ=0.6: 113→24 entities (catastrophic over-merge — "wait()", "signal()", "Lock" all collapsed)

Root cause: embedding similarity is unreliable for short entity names. Names like "Lock",
"Mutex", "Thread" occupy a compressed region of the semantic space, producing high cosine
similarity regardless of whether they refer to the same concept.

Graphiti (getzep/graphiti, 20k+ stars, Apache 2.0) solves this with a
**deterministic-first, LLM-last** pipeline using entropy-gated character Jaccard
instead of embedding similarity.

## Decision

Replace the embedding-based `EntityResolver` with a three-layer cascade:

### Layer 1: Exact normalized match (O(1) HashMap)
Lowercase + collapse whitespace. Identical names merge immediately.

### Layer 2: Entropy-gated 3-gram character Jaccard (θ=0.9)
Before fuzzy matching, check Shannon entropy of the entity name:
- Short/low-entropy names ("Lock", "Mutex", "API") → **skip fuzzy, send to LLM**
- High-entropy names ("Condition Variable", "Bounded Buffer") → 3-gram Jaccard at θ=0.9

This prevents the over-merging problem: related-but-distinct short names never reach
the fuzzy matcher.

### Layer 3: LLM batch dedup (one call per batch)
All unresolved singletons sent to LLM in one batch call. The LLM groups entities that
refer to the same real-world concept. This is O(1) LLM calls instead of O(N²) pairwise.

### Integration
Wired into `benchmark/scripts/cocoindex_spike.py` via `parallel_merge()`.
`enhanced_pipeline.py` integration deferred (same scope as ADR-0004).

## Alternatives Considered

### Alternative 1: Embedding cosine similarity (ADR-0004)
- **Why not**: Proved unreliable — no threshold balances under-merge vs over-merge for short names

### Alternative 2: Fuzzy string matching without entropy gate (fuzzywuzzy)
- **Why not**: Would over-merge short names the same way embedding did

### Alternative 3: LLM-only resolution
- **Why not**: O(N²) pairwise calls; Graphiti demonstrated that >90% of duplicates resolve deterministically

## Consequences

### Positive
- No more over-merging of short entity names (entropy gate)
- Strict Jaccard θ=0.9 only merges near-identical surface forms
- LLM handles genuinely ambiguous cases with full context
- Zero new dependencies (pure Python string ops for Layers 1-2)

### Negative
- Layer 3 adds 1-3 LLM calls per document (batch, not pairwise)
- Sequential resolution within each merge step (vs. embarrassingly parallel cosine matrix)
- Jaccard cannot catch semantic synonyms ("CV" ↔ "Condition Variable") — requires LLM

### Risks
- LLM batch prompt may need tuning for educational content vs. Graphiti's conversational context
- MinHash/LSH skipped at MVP scale; may need adding if entity count grows to 1000+

## Verification Checklist

- [ ] "Condition Variable" / "condition variable" → exact merge (Layer 1)
- [ ] "Bounded Buffer Problem" / "Bounded Buffer" → Jaccard merge (Layer 2)
- [ ] "Lock" / "Mutex" → NOT fuzzy-merged (low entropy); resolved by LLM (Layer 3)
- [ ] "wait()" / "signal()" → NOT merged (distinct concepts; LLM should keep separate)
- [ ] Entity count: ~15-30 range (not 78 or 24)
- [ ] Core node recall ≥ 95%
- [ ] Total LLM ER calls ≤ 3 per document

## Related

- [ADR-0004](ADR-0004-embedding-entity-resolution.md) — Superseded (embedding approach)
- [ADR-0003](ADR-0003-cocoindex-style-structured-extraction.md) — Source of entity duplication problem
- Knowledge source: graphiti-er-module (applied 2026-02-20)
- Evidence: getzep/graphiti `dedup_helpers.py`, `node_operations.py`
