"""Two-pass extraction: entities with cheap model, relations with strong model.

Pass 1: Entity extraction (Flash Lite) — proven high quality, low cost
Pass 2: Relation extraction (Flash) — needs stronger model for direction + type accuracy

Implements ADR-0006 tiered model strategy.
"""

import json
from typing import Optional

import litellm

from src.extraction.prompts import (
    ENTITY_ONLY_PROMPT,
    RELATION_PROMPT_TEMPLATE,
    EDGE_TYPES,
)


def extract_entities(
    text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """Pass 1: Extract entities only."""
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": ENTITY_ONLY_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    data = _parse_json(response.choices[0].message.content)
    return {
        "entities": data.get("entities", []),
        "tokens": {
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
        },
    }


def extract_relations(
    text: str,
    entities: list[dict],
    model: str = "gemini/gemini-2.5-flash",
) -> dict:
    """Pass 2: Extract relations given a fixed entity list."""
    # Build entity summary for the prompt
    entity_lines = []
    for e in entities:
        entity_lines.append(
            f'- {e["id"]} [{e["type"]}] "{e["label"]}": {e["definition"]}'
        )
    entity_list_str = "\n".join(entity_lines)

    system_prompt = RELATION_PROMPT_TEMPLATE.replace(
        "{entity_list}", entity_list_str
    )

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        max_tokens=16384,
        response_format={"type": "json_object"},
    )

    raw_content = response.choices[0].message.content
    # Debug: save raw response for inspection
    _debug_path = "/Users/waynewang/Graphex/experiments/results/v7-two-pass/_debug_pass2_raw.txt"
    import os; os.makedirs(os.path.dirname(_debug_path), exist_ok=True)
    with open(_debug_path, "w") as _f:
        _f.write(raw_content or "<None>")

    data = _parse_json(raw_content)
    relationships = data.get("relationships", [])

    # Post-validation: drop edges with illegal types
    valid_types = set(EDGE_TYPES)
    entity_ids = {e["id"] for e in entities}
    validated = []
    dropped = []

    for rel in relationships:
        rel_type = rel.get("type", "")
        src = rel.get("source", "")
        tgt = rel.get("target", "")

        issues = []
        if rel_type not in valid_types:
            issues.append(f"illegal_type:{rel_type}")
        if src not in entity_ids:
            issues.append(f"unknown_source:{src}")
        if tgt not in entity_ids:
            issues.append(f"unknown_target:{tgt}")
        if src == tgt:
            issues.append("self_loop")

        if issues:
            dropped.append({"relationship": rel, "issues": issues})
        else:
            validated.append(rel)

    return {
        "relationships": validated,
        "dropped": dropped,
        "tokens": {
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
        },
    }


def extract_two_pass(
    text: str,
    entity_model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    relation_model: str = "gemini/gemini-2.5-flash",
) -> dict:
    """Full two-pass extraction pipeline.

    Returns dict with: entities, relationships, dropped, tokens (combined).
    """
    # Pass 1: Entities
    pass1 = extract_entities(text, model=entity_model)
    entities = pass1["entities"]

    # Pass 2: Relations
    pass2 = extract_relations(text, entities, model=relation_model)

    # Combine token usage
    tokens = {
        "input": pass1["tokens"]["input"] + pass2["tokens"]["input"],
        "output": pass1["tokens"]["output"] + pass2["tokens"]["output"],
        "pass1_input": pass1["tokens"]["input"],
        "pass1_output": pass1["tokens"]["output"],
        "pass2_input": pass2["tokens"]["input"],
        "pass2_output": pass2["tokens"]["output"],
    }

    return {
        "entities": entities,
        "relationships": pass2["relationships"],
        "dropped": pass2.get("dropped", []),
        "tokens": tokens,
    }


def _clean_json_text(text: str) -> str:
    """Strip JS-style comments and trailing commas that Gemini sometimes emits."""
    import re
    # Remove single-line comments (// ...)
    text = re.sub(r'//[^\n]*', '', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _parse_json(text: str) -> dict:
    """Parse JSON with fallback extraction."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try cleaning comments/trailing commas
        cleaned = _clean_json_text(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON object from surrounding text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        return {"entities": [], "relationships": []}
