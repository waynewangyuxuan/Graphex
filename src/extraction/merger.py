"""Merge extraction results from multiple chunks using entity resolution.

Uses Graphiti-style cascading ER (ADR-0005) + parallel pairwise merge.
"""

from src.resolution.entity_resolver import EntityResolver
from src.resolution.parallel_merge import parallel_merge


def merge_chunk_results(
    chunk_results: list[dict],
    max_workers: int = 4,
    enable_llm_layer: bool = True,
) -> dict:
    """
    Merge results from multiple chunks using cascading entity resolution
    and O(log N) parallel pairwise merge.

    Args:
        chunk_results: List of dicts with keys: entities, relationships, tokens.
        max_workers: Thread pool size for parallel merge.
        enable_llm_layer: Whether to use LLM batch dedup (Layer 3).

    Returns:
        Dict with keys: entities, relationships, tokens.
    """
    total_tokens = {
        "input": sum(r["tokens"]["input"] for r in chunk_results),
        "output": sum(r["tokens"]["output"] for r in chunk_results),
    }

    kg_parts = [
        {"entities": r["entities"], "relationships": r["relationships"]}
        for r in chunk_results
    ]

    resolver = EntityResolver(enable_llm_layer=enable_llm_layer)
    merged_kg = parallel_merge(kg_parts, resolver, max_workers=max_workers)

    return {**merged_kg, "tokens": total_tokens}
