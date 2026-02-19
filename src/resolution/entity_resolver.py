"""
Three-layer cascading entity resolver.

Layer 1: Exact normalized match (label + type) — zero cost
Layer 2: Embedding cosine similarity — primary workhorse, θ=0.8
Layer 3: LLM fallback for gray-zone pairs [0.6, 0.8) — optional, Phase 2

Source: entity-resolution-module (iText2KG pattern, applied 2026-02-19)
Evidence: AuvaLab/itext2kg — embedding cosine similarity replaces LLM-based
resolution with 10x+ speed improvement.
"""

import re
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class EntityResolver:
    """
    Three-layer cascading entity resolver for KG deduplication.

    Operates on entity dicts with keys: id, label, type, definition, importance.
    Returns (deduplicated_entities, id_remap) where id_remap maps every input
    entity ID to the canonical entity ID it was merged into.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        threshold: float = 0.8,
        llm_fallback_range: tuple[float, float] = (0.6, 0.8),
        enable_llm_fallback: bool = False,
        llm_model: str = "gemini/gemini-2.0-flash",
    ) -> None:
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.llm_fallback_range = llm_fallback_range
        self.enable_llm_fallback = enable_llm_fallback
        self.llm_model = llm_model

    def resolve(
        self, entities: list[dict]
    ) -> tuple[list[dict], dict[str, str]]:
        """
        Deduplicate a list of entities using cascading matching.

        Args:
            entities: List of entity dicts (must each have an "id" key).

        Returns:
            (canonical_entities, id_remap)
            id_remap maps every input entity ID → canonical entity ID.
        """
        n = len(entities)
        if n == 0:
            return [], {}

        # Union-Find with path-halving
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path halving
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            pa, pb = find(a), find(b)
            if pa != pb:
                parent[pb] = pa

        # --- Layer 1: Exact normalized match ---
        norm_to_idx: dict[str, int] = {}
        for i, e in enumerate(entities):
            key = self._normalize(e.get("label", ""), e.get("type", ""))
            if key in norm_to_idx:
                union(i, norm_to_idx[key])
            else:
                norm_to_idx[key] = i

        # --- Layer 2: Embedding cosine similarity ---
        texts = [
            f"{e.get('label', '')}: {e.get('type', '')}" for e in entities
        ]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        sim_matrix = cosine_similarity(embeddings)  # (n, n) float matrix

        ambiguous: list[tuple[int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                if find(i) == find(j):
                    continue
                sim = float(sim_matrix[i, j])
                if sim >= self.threshold:
                    union(i, j)
                elif (
                    self.enable_llm_fallback
                    and self.llm_fallback_range[0] <= sim < self.llm_fallback_range[1]
                ):
                    ambiguous.append((i, j))

        # --- Layer 3: LLM fallback (optional) ---
        if self.enable_llm_fallback and ambiguous:
            for i, j in ambiguous:
                if find(i) != find(j) and self._llm_should_merge(
                    entities[i], entities[j]
                ):
                    union(i, j)

        # Build groups: root_index → [member_indices]
        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        # Merge each group into one canonical entity
        canonical_entities: list[dict] = []
        id_remap: dict[str, str] = {}

        for member_indices in groups.values():
            group = [entities[m] for m in member_indices]
            canonical = self._merge_group(group)
            canonical_entities.append(canonical)
            canonical_id = canonical["id"]
            for m in member_indices:
                id_remap[entities[m]["id"]] = canonical_id

        return canonical_entities, id_remap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize(self, label: str, entity_type: str) -> str:
        """Normalize (label, type) pair for exact matching (Layer 1)."""
        key = f"{label.lower()}:{entity_type.lower()}"
        return re.sub(r'[_"\-\s]+', " ", key).strip()

    def _merge_group(self, group: list[dict]) -> dict:
        """Merge a group of duplicate entities into one canonical entity."""
        if len(group) == 1:
            return dict(group[0])

        # Canonical base: entity with the longest label (more complete name)
        canonical = dict(max(group, key=lambda e: len(e.get("label", ""))))

        # Merge definitions: concatenate distinct non-empty definitions
        seen_defs: set[str] = set()
        merged_defs: list[str] = []
        for e in group:
            d = e.get("definition", "").strip()
            if d and d not in seen_defs:
                merged_defs.append(d)
                seen_defs.add(d)
        if merged_defs:
            canonical["definition"] = " | ".join(merged_defs)[:500]

        # Type: majority vote
        type_counts: dict[str, int] = {}
        for e in group:
            t = e.get("type", "")
            type_counts[t] = type_counts.get(t, 0) + 1
        canonical["type"] = max(type_counts, key=lambda t: type_counts[t])

        # Importance: highest wins (core > supporting > peripheral)
        rank = {"core": 3, "supporting": 2, "peripheral": 1}
        canonical["importance"] = max(
            (e.get("importance", "peripheral") for e in group),
            key=lambda x: rank.get(x, 0),
        )

        return canonical

    def _llm_should_merge(self, entity_a: dict, entity_b: dict) -> bool:
        """
        Layer 3: Ask LLM whether two ambiguous entities should be merged.
        Only called for similarity in [llm_fallback_range[0], llm_fallback_range[1]).
        """
        try:
            import litellm

            prompt = (
                "Are these two entities referring to the same concept?\n"
                f"Entity A: {entity_a.get('label')} ({entity_a.get('type')}) — "
                f"{entity_a.get('definition', '')}\n"
                f"Entity B: {entity_b.get('label')} ({entity_b.get('type')}) — "
                f"{entity_b.get('definition', '')}\n"
                "Answer YES or NO with a brief reason."
            )
            response = litellm.completion(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=64,
            )
            answer = response.choices[0].message.content.strip().upper()
            return answer.startswith("YES")
        except Exception:
            return False
