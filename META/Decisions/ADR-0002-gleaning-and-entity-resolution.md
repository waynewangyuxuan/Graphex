# ADR-0002: Adopt Gleaning and Description-Aggregation Entity Resolution

- **Status**: Proposed
- **Date**: 2026-02-18
- **Deciders**: Wayne Wang

## Context

EXP-001 benchmark (threads-cv document) revealed two critical gaps:

1. **Low recall**: Core node match rate is 37.5%. Single-pass LLM extraction systematically misses entities in information-dense text.
2. **Duplicate entities**: Cross-chunk extraction produces duplicate nodes for the same concept with no mechanism to merge their descriptions.

GraphRAG and nano-graphrag independently evolved identical solutions to these problems — Gleaning and description-aggregation entity merging — validating them as natural solutions to this problem domain. These patterns are documented and evidenced in `Prism output/kg-extraction-pipeline`.

## Decision

### 1. Gleaning (embed in Phase 2: Guided Extraction)

After the initial extraction round for a chunk, add up to `max_gleanings` continuation rounds:

```
if chunk.token_count > 500:
    for i in range(max_gleanings):
        more = llm("可能有遗漏的实体，请继续提取", chunk, current_entities)
        if more.is_empty or more.answer == "NO":
            break
        entities.extend(more.entities)
```

- `max_gleanings` is **adjustable** (not hardcoded); recommended starting value: `1`
- Only enabled for chunks >500 tokens; short chunks have low information density
- Each additional gleaning round approximately doubles token cost for that chunk

### 2. Phase 4: Entity Resolution (after Phase 3: Grounding Verification)

Pipeline becomes: First-Pass → Guided Extraction (+ Gleaning) → Grounding Verification → **Entity Resolution**

Resolution algorithm — type-aware description aggregation:

```
match_keys(entity) = [entity.label.lower()] + [a.lower() for a in entity.aliases]

merge_entity(existing, new_entity):
  if type conflict: existing.type = most_frequent_type
  existing.descriptions.append(new_entity.description)
  if token_count(descriptions) > THRESHOLD:
    existing.definition = llm_summarize(descriptions)  # cheap model ok
  existing.aliases = union(existing.aliases, new_entity.aliases)
  existing.sources.append(new_entity.source)
```

Edge normalization runs in the same pass:
- Weight accumulation: `merged_weight = sum(edge.weight)` for same entity pair
- Direction normalization: `key = tuple(sorted([src_id, tgt_id]))` to deduplicate undirected pairs

**Relationship to existing EntityRegistry**: Registry handles intra-run deduplication during extraction (exact match + embedding). Phase 4 handles post-hoc merging and description enrichment. They are complementary, not redundant. Embedding clustering (Technical.md §4.4) runs as an enhancement after description aggregation to catch synonym cases (e.g., "CV" vs "Condition Variable").

## Alternatives Considered

### Alternative 1: Embedding-only clustering (current design in Technical.md §4.4)

- **Pros**: Handles synonyms without exact name match; robust to paraphrasing
- **Cons**: Requires vector DB at merge time; higher latency; overkill for P0
- **Why not**: Kept as enhancement layer after description aggregation, not as replacement

### Alternative 2: Lexical groupby only (GraphRAG simple mode)

- **Pros**: Fast, deterministic, zero extra LLM calls
- **Cons**: Cannot handle aliases; Graphex schema already has an `aliases` field that should be used
- **Why not**: Description aggregation adds minimal complexity while being strictly more powerful

## Consequences

### Positive

- Core node recall expected to rise from ~37% to 55-65% (1 Gleaning round, based on GraphRAG empirical data)
- Eliminates duplicate nodes from multi-chunk extraction
- Description enrichment produces richer node definitions for UI display
- Lays groundwork for multi-document synthesis (Feature 6): cross-doc entity merging uses the same Phase 4 mechanism

### Negative

- Gleaning approximately doubles token cost for long chunks (cost scales with `max_gleanings`)
- Phase 4 adds wall-clock latency proportional to duplicate entity count

### Risks

- `max_gleanings` set too high: diminishing returns + cost explosion. **Mitigation**: expose as config parameter, document recommended range (1-2), default to 1.
- Description over-merging loses nuanced distinctions between similar-but-different entities. **Mitigation**: retain per-chunk `sources` field for traceability; keep embedding clustering as a second-pass sanity check.

## Related

- [Technical.md §3.3](../Core/Technical.md) — Entity Extractor Agent spec (Gleaning parameters added here)
- [Technical.md §4.4](../Core/Technical.md) — Cross-chunk entity resolution design (description aggregation added as P0 strategy)
- [Research/KG_Pipeline_Patterns.md](../Research/KG_Pipeline_Patterns.md) — Full pattern reference with P1/P2 roadmap
- Knowledge source: Prism output/kg-extraction-pipeline (applied 2026-02-18)
