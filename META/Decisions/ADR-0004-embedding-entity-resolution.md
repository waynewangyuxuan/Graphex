# ADR-0004: Embedding-Based Entity Resolution (iText2KG Pattern)

- **Status**: Accepted
- **Date**: 2026-02-19
- **Deciders**: Wayne Wang

## Context

ADR-0003 showed the CocoIndex-style extraction achieves 100% core node recall but produces
113 raw entities vs. 17 ground truth nodes — a 6.6× duplication ratio. The next bottleneck
is entity resolution: merging "Mutex", "Mutex Lock", and "Lock" into one canonical entity.

ADR-0002 adopted **description-aggregation** (label + alias exact matching) as the P0
entity resolution strategy for `enhanced_pipeline.py`, with embedding-based clustering
noted as an enhancement layer. This ADR implements that enhancement.

The reference implementation is **iText2KG** (AuvaLab, 1.2k+ stars, MIT-like), which
demonstrated that embedding cosine similarity fully replaces LLM-based entity resolution
with a 10x+ speed improvement. Their pattern:

1. Exact normalized match (zero cost)
2. Embedding cosine similarity on `"label: type"` text (primary workhorse)
3. LLM fallback for ambiguous gray-zone pairs (high cost, low frequency)

Combined with **parallel pairwise merge** (binary reduction), N chunk KGs collapse in
O(log N) rounds instead of O(N) sequential passes.

## Decision

Implement `src/resolution/` with two modules:

### 1. `EntityResolver` — Three-layer cascading matcher

```
Layer 1: normalize(label + type) exact match → Union-Find merge
Layer 2: cosine_similarity(embed("label: type")) ≥ θ=0.8 → Union-Find merge
Layer 3: LLM("Are these the same concept?") for sim ∈ [0.6, 0.8) → optional
```

Merge policy for a group:
- **Label**: longest wins ("Condition Variable" > "CV")
- **Definition**: concatenate distinct definitions, cap at 500 chars
- **Type**: majority vote across group members
- **Importance**: highest wins (core > supporting > peripheral)

### 2. `parallel_merge()` — Binary reduction

```
[KG1..KG8] → [KG12, KG34, KG56, KG78] → [KG1234, KG5678] → [KG_final]
```

Each round uses `ThreadPoolExecutor`. Entity IDs are prefixed with chunk index
(`c0_`, `c1_`, …) before the first round to prevent accidental ID collisions.

### Integration scope (this ADR)

Wired into `benchmark/scripts/cocoindex_spike.py` only:
- `merge_chunk_results()` replaced with `parallel_merge()` + `EntityResolver`
- Expected: 113 raw entities → ~20–25 canonical entities
- `enhanced_pipeline.py` Phase 4 integration deferred (ADR-0002 label-match stays as P0)

## Alternatives Considered

### Alternative 1: Fuzzy string matching (fuzzywuzzy / graphrag-psql pattern)
- **Pros**: No model dependency; pure string ops
- **Cons**: Cannot handle "CV" ↔ "Condition Variable"; same limitation as current exact match
- **Why not**: Embedding captures semantic similarity that string matching cannot

### Alternative 2: LLM as primary resolver
- **Pros**: Highest accuracy for ambiguous cases
- **Cons**: 100 entity pairs = 100 LLM calls; 10x+ slower; rate-limited
- **Why not**: iText2KG proved embedding cosine achieves equivalent accuracy at 10x speed

### Alternative 3: Neo4j k-NN + weakly connected components
- **Pros**: Scales to millions of entities; production-grade
- **Cons**: Requires Neo4j; overkill for MVP scale (<500 entities per document)
- **Why not**: MVP uses NetworkX in-memory; upgrade path is interface-compatible

## Consequences

### Positive
- Expected: ~6.6× entity count reduction (113 → ~20–25) on threads-cv benchmark
- Edge recall expected to improve (entity alignment unlocks more edge matches)
- O(log N) merge vs. O(N) sequential; parallelized within each round
- Embedding model (`all-MiniLM-L6-v2`) runs on CPU; 113 entities ≈ 50ms encoding

### Negative
- New dependency: `sentence-transformers` (~500MB model download on first use)
- ~2s startup latency for model load (one-time per process)
- Threshold θ=0.8 is a starting point; needs benchmark calibration

### Risks
- **Over-merging**: "Lock" and "Lock-free" merged incorrectly if threshold too low.
  Mitigation: type field included in embedding text; benchmark precision monitored.
- **Gray-zone pairs**: similarity 0.6–0.8 left unresolved (LLM fallback disabled by default).
  Mitigation: enable `enable_llm_fallback=True` for production runs after cost evaluation.

## Verification Checklist

- [ ] "Lock" / "Mutex" / "Mutex Lock" merge into one entity
- [ ] "Producer Thread" / "Producer" merge; "Producer/Consumer" stays separate
- [ ] "Python: Language" vs "Python: Snake" not merged (different type in embedding text)
- [ ] threads-cv: 113 entities → ~20–25 entities; core node recall ≥ 100%
- [ ] Core edge recall ≥ 60% (post entity alignment)
- [ ] `entity_resolution` total time < 2s (excluding LLM fallback)

## Related

- [ADR-0002](ADR-0002-gleaning-and-entity-resolution.md) — Description-aggregation P0 strategy (this ADR is the enhancement layer)
- [ADR-0003](ADR-0003-cocoindex-style-structured-extraction.md) — CocoIndex spike (source of the 113-entity problem)
- [Research/KG_Pipeline_Patterns.md](../Research/KG_Pipeline_Patterns.md) — Phase 4 implementation note
- Knowledge source: Prism entity-resolution-module (applied 2026-02-19)
- Evidence: AuvaLab/itext2kg — https://arxiv.org/html/2409.03284v1
