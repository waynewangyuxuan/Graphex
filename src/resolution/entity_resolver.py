"""
Graphiti-style three-layer cascading entity resolver.

Layer 1: Exact normalized match — O(1) HashMap lookup
Layer 2: Entropy-gated character 3-gram Jaccard — strict θ=0.9
Layer 3: LLM batch dedup — one call per batch of unresolved entities

Key insight from Graphiti (getzep/graphiti, 20k+ stars): embedding cosine
similarity is unreliable for short entity names. Character-level Jaccard
with an entropy gate prevents over-merging while catching surface-form
variations.

Source: graphiti-er-module, applied 2026-02-20.
Supersedes: iText2KG embedding-based approach (ADR-0004).
"""

import json
import math
import re
from collections import Counter

import litellm


# --- Constants (from Graphiti dedup_helpers.py) ---
_ENTROPY_THRESHOLD = 1.5
_MIN_NAME_LENGTH = 6
_MIN_TOKEN_COUNT = 2
_JACCARD_THRESHOLD = 0.9
_DEFAULT_LLM_MODEL = "gemini/gemini-2.5-flash-lite-preview-09-2025"


class EntityResolver:
    """
    Three-layer cascading entity resolver for KG deduplication.

    Operates on entity dicts with keys: id, label, type, definition, importance.
    Returns (deduplicated_entities, id_remap) where id_remap maps every input
    entity ID to the canonical entity ID it was merged into.
    """

    def __init__(
        self,
        enable_llm_layer: bool = True,
        llm_model: str = _DEFAULT_LLM_MODEL,
        jaccard_threshold: float = _JACCARD_THRESHOLD,
    ) -> None:
        self.enable_llm_layer = enable_llm_layer
        self.llm_model = llm_model
        self.jaccard_threshold = jaccard_threshold

    def resolve(
        self, entities: list[dict]
    ) -> tuple[list[dict], dict[str, str]]:
        """
        Deduplicate entities using three-layer cascading resolution.

        Returns:
            (canonical_entities, id_remap)
        """
        n = len(entities)
        if n == 0:
            return [], {}

        # Union-Find
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            pa, pb = find(a), find(b)
            if pa != pb:
                parent[pb] = pa

        # --- Layer 1: Exact normalized match ---
        norm_to_idx: dict[str, int] = {}
        for i, e in enumerate(entities):
            key = _normalize_exact(e.get("label", ""))
            if key in norm_to_idx:
                union(i, norm_to_idx[key])
            else:
                norm_to_idx[key] = i

        # --- Layer 2: Entropy-gated 3-gram Jaccard ---
        unresolved_layer2: list[int] = []
        for i in range(n):
            if find(i) != i:
                continue  # already merged
            label_i = entities[i].get("label", "")
            if not _has_high_entropy(label_i):
                unresolved_layer2.append(i)
                continue
            shingles_i = _shingles(label_i)
            for j in range(i + 1, n):
                if find(i) == find(j):
                    continue
                label_j = entities[j].get("label", "")
                if not _has_high_entropy(label_j):
                    continue
                sim = _jaccard(shingles_i, _shingles(label_j))
                if sim >= self.jaccard_threshold:
                    union(i, j)

        # Collect indices still unresolved after Layer 2
        # (roots that were low-entropy OR didn't match anything)
        resolved_roots = set()
        for i in range(n):
            root = find(i)
            resolved_roots.add(root)

        # Find entities that are singletons (root == self, group size 1)
        singleton_indices: list[int] = []
        groups_pre_llm: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            groups_pre_llm.setdefault(root, []).append(i)
        for root, members in groups_pre_llm.items():
            if len(members) == 1:
                singleton_indices.append(root)

        # --- Layer 3: LLM batch dedup ---
        if self.enable_llm_layer and len(singleton_indices) > 1:
            self._llm_batch_dedup(entities, singleton_indices, parent, find, union)

        # Build final groups
        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        canonical_entities: list[dict] = []
        id_remap: dict[str, str] = {}
        for member_indices in groups.values():
            group = [entities[m] for m in member_indices]
            canonical = _merge_group(group)
            canonical_entities.append(canonical)
            for m in member_indices:
                id_remap[entities[m]["id"]] = canonical["id"]

        return canonical_entities, id_remap

    def _llm_batch_dedup(
        self,
        entities: list[dict],
        singleton_indices: list[int],
        parent: list[int],
        find,
        union,
    ) -> None:
        """
        Layer 3: Send all unresolved singletons to LLM in one batch call.
        LLM decides which entities are duplicates of each other.
        """
        if len(singleton_indices) < 2:
            return

        # Build the prompt with all singletons
        entity_lines = []
        for idx in singleton_indices:
            e = entities[idx]
            entity_lines.append(
                f"  - ID: {idx} | Label: {e.get('label', '')} | "
                f"Type: {e.get('type', '')} | "
                f"Definition: {e.get('definition', '')[:120]}"
            )

        prompt = (
            "You are deduplicating entities extracted from a document.\n\n"
            "ENTITIES (each with a numeric ID):\n"
            + "\n".join(entity_lines)
            + "\n\n"
            "Find groups of entities that refer to the SAME real-world "
            "concept or object. Only group entities that are truly the same "
            "thing — do NOT group entities that are merely related.\n\n"
            'Return JSON: {"groups": [[id1, id2], [id3, id4, id5], ...]}\n'
            "Each group contains the numeric IDs of duplicate entities.\n"
            "Entities with no duplicates should NOT appear in any group.\n"
            "Return ONLY valid JSON, no markdown fences."
        )

        try:
            response = litellm.completion(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content
            data = json.loads(text)
            groups = data.get("groups", [])

            valid_set = set(singleton_indices)
            for group in groups:
                # Validate: all IDs must be valid singleton indices
                valid_ids = [int(x) for x in group if int(x) in valid_set]
                if len(valid_ids) < 2:
                    continue
                anchor = valid_ids[0]
                for other in valid_ids[1:]:
                    union(anchor, other)
        except Exception:
            pass  # Layer 3 failure is non-fatal; entities stay as-is


# ------------------------------------------------------------------
# Module-level helpers (no state)
# ------------------------------------------------------------------


def _normalize_exact(name: str) -> str:
    """Normalize for exact matching: lowercase + collapse whitespace."""
    return re.sub(r"\s+", " ", name.lower().strip())


def _normalize_fuzzy(name: str) -> str:
    """Normalize for fuzzy matching: keep alphanumerics + spaces only."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _shannon_entropy(text: str) -> float:
    """Character-level Shannon entropy (spaces stripped)."""
    chars = text.replace(" ", "")
    if not chars:
        return 0.0
    counts = Counter(chars)
    total = len(chars)
    return -sum(
        (c / total) * math.log2(c / total) for c in counts.values()
    )


def _has_high_entropy(name: str) -> bool:
    """
    Entropy gate: short/repetitive names bypass fuzzy matching.

    "Lock", "Mutex", "API", "Thread" → low entropy → skip to LLM.
    "Condition Variable", "Bounded Buffer" → high entropy → Jaccard OK.
    """
    normalized = _normalize_fuzzy(name)
    tokens = normalized.split()
    if len(normalized) < _MIN_NAME_LENGTH and len(tokens) < _MIN_TOKEN_COUNT:
        return False
    return _shannon_entropy(normalized) >= _ENTROPY_THRESHOLD


def _shingles(name: str, n: int = 3) -> set[str]:
    """Character n-gram shingles."""
    norm = _normalize_fuzzy(name)
    if len(norm) < n:
        return {norm}
    return {norm[i : i + n] for i in range(len(norm) - n + 1)}


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union_size = len(set_a | set_b)
    return intersection / union_size if union_size else 0.0


def _merge_group(group: list[dict]) -> dict:
    """Merge a group of duplicate entities into one canonical entity."""
    if len(group) == 1:
        return dict(group[0])

    canonical = dict(max(group, key=lambda e: len(e.get("label", ""))))

    seen_defs: set[str] = set()
    merged_defs: list[str] = []
    for e in group:
        d = e.get("definition", "").strip()
        if d and d not in seen_defs:
            merged_defs.append(d)
            seen_defs.add(d)
    if merged_defs:
        canonical["definition"] = " | ".join(merged_defs)[:500]

    type_counts: dict[str, int] = {}
    for e in group:
        t = e.get("type", "")
        type_counts[t] = type_counts.get(t, 0) + 1
    canonical["type"] = max(type_counts, key=lambda t: type_counts[t])

    rank = {"core": 3, "supporting": 2, "peripheral": 1}
    canonical["importance"] = max(
        (e.get("importance", "peripheral") for e in group),
        key=lambda x: rank.get(x, 0),
    )

    return canonical
