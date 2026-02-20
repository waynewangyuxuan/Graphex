# Graphiti Entity Resolution Pipeline — Knowledge Module

> Source: [getzep/graphiti](https://github.com/getzep/graphiti) (20k+ stars, Apache 2.0)
> Extracted: 2026-02-20

## Core Pattern: Three-Layer Cascading Entity Resolution

Graphiti's ER is a **deterministic-first, LLM-last** pipeline. The key insight: most entity duplicates can be resolved cheaply without LLM calls; only ambiguous cases need expensive model inference.

### Layer 1: Exact Match (O(1) lookup)

```
normalize(name) → lowercase + collapse whitespace
lookup in HashMap<normalized_name, [EntityNode]>
  → 1 match  → resolved (done)
  → 0 match  → pass to Layer 2
  → >1 match → skip to Layer 3 (ambiguous, needs LLM)
```

### Layer 2: Entropy-Gated Fuzzy Match (MinHash/LSH + Jaccard)

**Critical innovation**: Before fuzzy matching, check if the entity name has enough **Shannon entropy** to be reliably compared:

```python
def _has_high_entropy(name: str) -> bool:
    # Short, repetitive names (e.g., "Lock", "API", "Node") are UNRELIABLE
    # for fuzzy matching — they produce false positives
    if len(name) < 6 and token_count < 2:
        return False
    return shannon_entropy(name) >= 1.5  # threshold
```

**Why this matters for us**: Our spike has entities like "Lock", "Mutex", "Thread" — these are short, low-entropy names that should NOT be fuzzy-matched. Graphiti sends them straight to LLM instead.

For high-entropy names, the fuzzy pipeline is:
1. **3-gram shingling**: `"condition variable"` → `{"con","ond","ndi","dit","iti","tio","ion","on ","n v","var",...}`
2. **MinHash signatures**: 32 permutations, fast approximate set similarity
3. **LSH banding**: band_size=4, groups candidates into buckets for O(1) lookup
4. **Jaccard verification**: threshold ≥ 0.9 (very strict — almost identical names only)

Unresolved → pass to Layer 3.

### Layer 3: LLM Resolution (fallback)

Only entities that failed both exact and fuzzy matching reach the LLM. The prompt design:

```
Given ENTITIES (extracted from current episode) and EXISTING ENTITIES (from graph):
- Only mark as duplicates if they refer to the SAME real-world object/concept
- Do NOT mark as duplicates if related but distinct
- Return: {id, best_name, duplicate_name_from_existing_or_empty}
```

Key prompt features:
- Includes **episode context** (the source text) so the LLM can disambiguate
- Processes **batch of unresolved entities** in one call (not pairwise)
- Returns `empty string` for non-duplicates (safe default)
- Defensive parsing: ignores malformed/duplicate LLM responses

### Candidate Retrieval (before resolution)

Graphiti doesn't compare against ALL existing entities. For each extracted entity:
1. **Hybrid search** (embedding + BM25 keyword) finds top-K similar candidates from graph DB
2. Candidates are deduplicated and indexed
3. Resolution only runs against this candidate set

This is crucial for scalability — comparing against 10K+ entities would be impractical.

## Pipeline Flow (per episode/chunk)

```
Extract entities (LLM)
    ↓
For each entity, hybrid search → candidate set
    ↓
Build candidate indexes (exact map + shingles + LSH buckets)
    ↓
Layer 1: exact match  →  resolved
    ↓ (unresolved)
Layer 2: entropy gate → high entropy → MinHash/Jaccard  →  resolved
                       → low entropy  → skip to Layer 3
    ↓ (unresolved)
Layer 3: batch LLM dedupe  →  resolved
    ↓ (still unresolved)
Treat as new entity
```

## Key Design Decisions & Trade-offs

### 1. No Embedding Cosine Similarity for ER
Graphiti does NOT use embedding cosine similarity for entity resolution (unlike iText2KG). Instead it uses character-level n-gram Jaccard via MinHash/LSH. Why?
- Embedding similarity is unreliable for short entity names (semantic space is too compressed)
- MinHash/Jaccard on character n-grams catches typos and surface-form variations
- But it's gated by entropy to avoid false positives on short names

### 2. Strict Fuzzy Threshold (0.9 Jaccard)
The fuzzy threshold is very high — only near-identical names pass. This prevents over-merging. The philosophy: **it's better to send more to the LLM than to merge incorrectly**.

### 3. Batch LLM Dedup (not pairwise)
Unresolved entities are sent to the LLM in one batch call, not N pairwise comparisons. This is O(1) LLM calls per chunk instead of O(N²).

### 4. Edge Resolution is Separate
Edges are resolved AFTER node resolution. Edge dedup uses:
- Same source+target node pair constraint
- Hybrid search for similar existing edges
- LLM determines: duplicate / contradicted / new

### 5. No Cross-Chunk Parallel Merge Needed
Graphiti processes episodes sequentially against a persistent graph DB. Each episode resolves against the FULL existing graph. This avoids the binary-tree merge problem entirely, but it IS sequential.

**For our use case**: We want parallel extraction. So we need to adapt: extract in parallel, then resolve against a growing in-memory entity registry (not a graph DB).

## Applicability to Graphex

### What to adopt:
1. **Entropy-gated fuzzy matching** — solves our over-merge problem for short entity names ("Lock", "Mutex", "Thread")
2. **Three-layer cascade** — exact → fuzzy → LLM, with strict gates between layers
3. **Batch LLM dedup prompt** — one call per batch of unresolved entities
4. **Strict Jaccard threshold (0.9)** — prevent fuzzy over-merging

### What to adapt:
1. **No graph DB** — we resolve in-memory, not against Neo4j
2. **Parallel extraction** — we extract all chunks in parallel, then resolve post-hoc
3. **Candidate retrieval** — we don't have a graph DB for hybrid search; use embedding ANN or brute-force on our ~100 entity scale
4. **MinHash may be overkill** — at our scale (~100 entities per document), brute-force Jaccard on shingles is fast enough without LSH

### What to skip:
1. Edge invalidation / temporal tracking (not MVP)
2. Community detection (not MVP)
3. Saga / episode ordering (not our use case)
