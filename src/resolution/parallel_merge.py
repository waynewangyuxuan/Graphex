"""
Parallel pairwise merge for chunk KGs using binary reduction.

Reduces N chunk KGs to 1 in O(log N) rounds, merging pairs concurrently
via ThreadPoolExecutor. Each merge uses EntityResolver (Graphiti-style
cascading: exact → entropy-gated Jaccard → LLM batch dedup).

Source: entity-resolution-module + graphiti-er-module.
"""

from concurrent.futures import ThreadPoolExecutor

from .entity_resolver import EntityResolver


def merge_two_kgs(kg_a: dict, kg_b: dict, resolver: EntityResolver) -> dict:
    """
    Merge two KG dicts using the entity resolver.

    Args:
        kg_a, kg_b: Dicts with {"entities": [...], "relationships": [...]}.
                    Entity IDs must be globally unique across both KGs.
        resolver: EntityResolver instance (shared across merge rounds).

    Returns:
        Merged KG dict with deduplicated entities and remapped relationships.
    """
    combined_entities = kg_a["entities"] + kg_b["entities"]
    combined_relationships = kg_a["relationships"] + kg_b["relationships"]

    canonical_entities, id_remap = resolver.resolve(combined_entities)

    # Remap relationship source/target to canonical IDs, drop self-loops
    remapped: list[dict] = []
    for rel in combined_relationships:
        src = id_remap.get(rel.get("source", ""), rel.get("source", ""))
        tgt = id_remap.get(rel.get("target", ""), rel.get("target", ""))
        if src and tgt and src != tgt:
            remapped.append({**rel, "source": src, "target": tgt})

    # Deduplicate relationships (same source + target + type)
    seen: set[tuple] = set()
    unique_rels: list[dict] = []
    for rel in remapped:
        key = (rel["source"], rel["target"], rel.get("type", ""))
        if key not in seen:
            seen.add(key)
            unique_rels.append(rel)

    return {"entities": canonical_entities, "relationships": unique_rels}


def _make_unique_ids(chunk_kgs: list[dict]) -> list[dict]:
    """
    Prefix entity IDs with chunk index to ensure global uniqueness.

    Chunk-local IDs like "e1" become "c0_e1", "c1_e1", etc., preventing
    accidental merges caused by ID collision across chunks.
    """
    result = []
    for i, kg in enumerate(chunk_kgs):
        prefix = f"c{i}_"
        id_map = {e["id"]: prefix + e["id"] for e in kg["entities"]}
        new_entities = [{**e, "id": id_map[e["id"]]} for e in kg["entities"]]
        new_rels = [
            {
                **r,
                "source": id_map.get(r.get("source", ""), r.get("source", "")),
                "target": id_map.get(r.get("target", ""), r.get("target", "")),
            }
            for r in kg["relationships"]
        ]
        result.append({"entities": new_entities, "relationships": new_rels})
    return result


def parallel_merge(
    chunk_kgs: list[dict],
    resolver: EntityResolver,
    max_workers: int = 4,
) -> dict:
    """
    Binary reduction merge: O(log N) rounds, each round parallelized.

    Example with 8 chunks:
        [KG1..KG8] → [KG12, KG34, KG56, KG78]  (4 parallel merges)
                   → [KG1234, KG5678]            (2 parallel merges)
                   → [KG_final]                   (1 merge)

    Args:
        chunk_kgs: Per-chunk KG dicts (entities + relationships).
        resolver: EntityResolver instance (created once, reused every round).
        max_workers: ThreadPoolExecutor parallelism per round.

    Returns:
        Single merged KG dict.
    """
    if not chunk_kgs:
        return {"entities": [], "relationships": []}
    if len(chunk_kgs) == 1:
        return chunk_kgs[0]

    # Ensure all entity IDs are globally unique before first merge
    current = _make_unique_ids(chunk_kgs)

    while len(current) > 1:
        pairs = [
            (current[i], current[i + 1]) for i in range(0, len(current) - 1, 2)
        ]
        leftover = current[-1] if len(current) % 2 else None

        with ThreadPoolExecutor(max_workers=min(max_workers, len(pairs))) as ex:
            merged = list(
                ex.map(lambda p: merge_two_kgs(p[0], p[1], resolver), pairs)
            )

        if leftover:
            merged.append(leftover)
        current = merged

    return current[0]
