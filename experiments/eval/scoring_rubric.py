"""Scoring rubric for narrative extraction evaluation.

Each document gets scored on 7 dimensions (1-10 scale).
Scores are assigned manually after reading both the source document
and the generated graph + tree.

The rubric is designed to be fast: ~5 min per document.
"""

RUBRIC = {
    "narrative_coverage": {
        "weight": 2.0,
        "description": "Does the graph capture the document's main narrative arc?",
        "scoring": {
            10: "Every major point in the document is represented",
            7: "Most major points captured, 1-2 minor gaps",
            5: "Core argument is there but significant sections missing",
            3: "Fragmented — key parts of the argument are absent",
            1: "Narrative is unrecognizable from the extraction",
        },
    },
    "segment_quality": {
        "weight": 1.5,
        "description": "Are individual segments well-scoped and well-summarized?",
        "scoring": {
            10: "Every segment is a clear, atomic teaching unit",
            7: "Most segments are clean; a few are too broad or too narrow",
            5: "Mixed — some good segments, some that merge or split topics poorly",
            3: "Many segments are vague, overlapping, or misscoped",
            1: "Segments don't correspond to meaningful units of the text",
        },
    },
    "relation_accuracy": {
        "weight": 1.5,
        "description": "Are discourse relations semantically correct?",
        "scoring": {
            10: "All relations accurately describe the rhetorical connection",
            7: "Most correct; 1-2 mislabeled types",
            5: "~70% correct; some relations feel forced or wrong",
            3: "Many relations are wrong or missing critical connections",
            1: "Relations don't reflect the actual document structure",
        },
    },
    "tree_structure": {
        "weight": 2.0,
        "description": "Does the tree reflect a natural reading hierarchy?",
        "scoring": {
            10: "Spine = perfect summary path; branches = natural depth control",
            7: "Spine is mostly right; 1-2 segments misplaced (spine↔branch)",
            5: "Spine misses some key points or includes too many details",
            3: "Tree structure doesn't match the document's teaching flow",
            1: "Tree is flat or deeply wrong — no reading benefit",
        },
    },
    "concept_extraction": {
        "weight": 1.0,
        "description": "Are concepts correctly identified and labeled?",
        "scoring": {
            10: "All key concepts present, no duplicates, roles accurate",
            7: "Good coverage; minor label inconsistencies or 1-2 missing",
            5: "Core concepts present but fragmented labels or wrong roles",
            3: "Many concepts missing or mislabeled",
            1: "Concept layer is unusable",
        },
    },
    "dedup_quality": {
        "weight": 1.0,
        "description": "Are chunk-overlap duplicates handled correctly?",
        "scoring": {
            10: "No visible duplicates; review merges are all correct",
            7: "1-2 near-duplicates remain; no bad merges",
            5: "A few duplicates OR 1 bad merge (lost content)",
            3: "Multiple duplicates or aggressive merges that lost content",
            1: "Severe duplication or destructive merging",
        },
    },
    "anchor_binding": {
        "weight": 1.0,
        "description": "Can segments be traced back to source text?",
        "scoring": {
            10: ">90% anchors resolve; source_ranges are accurate",
            7: "70-90% anchors resolve; ranges mostly correct",
            5: "50-70% resolve; some ranges clearly wrong",
            3: "<50% resolve; binding is unreliable",
            1: "Anchors don't work — can't find segments in source",
        },
    },
}

TOTAL_WEIGHT = sum(r["weight"] for r in RUBRIC.values())


def compute_score(scores: dict[str, int]) -> dict:
    """Compute weighted score from dimension scores.

    Args:
        scores: dict mapping dimension name → score (1-10)

    Returns:
        dict with per-dimension weighted scores, total, and grade
    """
    details = {}
    total = 0.0

    for dim, rubric in RUBRIC.items():
        raw = scores.get(dim, 0)
        weighted = raw * rubric["weight"]
        details[dim] = {
            "raw": raw,
            "weight": rubric["weight"],
            "weighted": weighted,
        }
        total += weighted

    max_possible = TOTAL_WEIGHT * 10
    pct = (total / max_possible) * 100

    # Grade
    if pct >= 85:
        grade = "A"
    elif pct >= 70:
        grade = "B"
    elif pct >= 55:
        grade = "C"
    elif pct >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "dimensions": details,
        "total_weighted": total,
        "max_possible": max_possible,
        "percentage": round(pct, 1),
        "grade": grade,
    }


# ── Quick scoring template ──

SCORE_TEMPLATE = """\
# Evaluation: {doc_id} — {doc_title}
# Date: {date}
# Evaluator: manual

## Scores (1-10)
narrative_coverage:
segment_quality:
relation_accuracy:
tree_structure:
concept_extraction:
dedup_quality:
anchor_binding:

## Notes
### What worked well:


### What failed:


### Suggestions:

"""
