# Graphiti ER Pipeline — Evidence

> All references to `getzep/graphiti` repository, commit at clone time 2026-02-20.

## Core ER Logic

### dedup_helpers.py — Deterministic Resolution Engine
**File**: `graphiti_core/utils/maintenance/dedup_helpers.py`

- `_normalize_string_exact()` (L39-42): lowercase + collapse whitespace
- `_normalize_name_for_fuzzy()` (L45-49): keep alphanumerics + apostrophes only
- `_name_entropy()` (L52-76): Shannon entropy over characters (spaces stripped)
- `_has_high_entropy()` (L79-85): gate check — `len < 6 AND tokens < 2 → False`, `entropy < 1.5 → False`
- `_shingles()` (L88-94): 3-gram character shingles
- `_minhash_signature()` (L103-114): 32-permutation MinHash via blake2b
- `_lsh_bands()` (L117-128): band_size=4, splits signature into LSH buckets
- `_jaccard_similarity()` (L131-140): exact set Jaccard
- `_build_candidate_indexes()` (L170-195): precomputes exact map + shingles + LSH for all candidates
- `_resolve_with_similarity()` (L198-246): the main cascade — exact → entropy gate → LSH candidates → Jaccard ≥ 0.9

**Key constants**:
```python
_NAME_ENTROPY_THRESHOLD = 1.5
_MIN_NAME_LENGTH = 6
_MIN_TOKEN_COUNT = 2
_FUZZY_JACCARD_THRESHOLD = 0.9
_MINHASH_PERMUTATIONS = 32
_MINHASH_BAND_SIZE = 4
```

### node_operations.py — Orchestration
**File**: `graphiti_core/utils/maintenance/node_operations.py`

- `resolve_extracted_nodes()` (L398-448): main entry point
  1. `_collect_candidate_nodes()` — hybrid search per extracted entity name
  2. `_build_candidate_indexes()` — precompute lookup structures
  3. `_resolve_with_similarity()` — deterministic pass (exact + fuzzy)
  4. `_resolve_with_llm()` — LLM fallback for unresolved
  5. Fallback: any still-unresolved → treat as new entity

- `_resolve_with_llm()` (L244-396): builds context with entity types + descriptions, calls `dedupe_nodes.nodes()` prompt, defensively parses response

- `_collect_candidate_nodes()` (L209-241): parallel hybrid search per entity name, deduplicates results

### dedupe_nodes.py — LLM Prompts
**File**: `graphiti_core/prompts/dedupe_nodes.py`

- `nodes()` (L110-176): batch dedup prompt — takes ENTITIES + EXISTING ENTITIES, returns `{id, name, duplicate_name}` per entity. Key instructions:
  - "Only considered duplicates if they refer to the *same real-world object or concept*"
  - "Do NOT mark as duplicates if related but distinct"
  - "MUST include EXACTLY N resolutions"
  - Response model: `NodeResolutions` with `entity_resolutions: list[NodeDuplicate]`

- `node()` (L53-107): single-entity dedup (used for add_episode path)
- `node_list()` (L179-213): UUID-based dedup for bulk operations

### dedupe_edges.py — Edge Resolution Prompt
**File**: `graphiti_core/prompts/dedupe_edges.py`

- `resolve_edge()` (L43-93): determines if new edge is duplicate/contradicted against existing edges between same entity pair. Returns `{duplicate_facts: [idx], contradicted_facts: [idx]}`.

### graphiti.py — Pipeline Orchestration
**File**: `graphiti_core/graphiti.py`

- `add_episode()` (L788-1007): single episode pipeline:
  1. Extract nodes (L930-937)
  2. Resolve nodes (L939-945) — calls `resolve_extracted_nodes()`
  3. Extract edges + resolve edges (L948-962)
  4. Extract attributes + summaries (L968-975)
  5. Save to graph DB

- `add_episode_bulk()` (L1037+): batch pipeline with separate dedup path

## Architecture Observations

1. **No embedding cosine for ER**: Graphiti embeds entity names for graph DB search/retrieval, but does NOT use embedding similarity for the actual dedup decision. The dedup decision uses character-level Jaccard or LLM.

2. **Candidate retrieval ≠ resolution**: Hybrid search (embedding + BM25) finds candidates; Jaccard/LLM resolves duplicates. These are separate steps.

3. **Sequential per-episode**: `add_episode` processes one episode at a time against the full graph. `add_episode_bulk` extracts in parallel but still resolves against accumulated state.

4. **Defensive LLM parsing**: L357-395 in node_operations.py — validates IDs, skips duplicates, warns on missing/extra, falls back to "new entity" on any parse error.
