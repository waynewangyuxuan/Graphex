"""Single-call structured extraction: one LLM call per chunk → entities + relationships.

Pattern: CocoIndex-style ExtractByLlm (ADR-0003).
"""

import json

import litellm

from src.extraction.prompts import EXTRACTION_INSTRUCTION


def extract_chunk(
    chunk_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
) -> dict:
    """
    Extract entities and relationships from a single text chunk.

    Returns dict with keys: entities, relationships, tokens.
    """
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_INSTRUCTION},
            {"role": "user", "content": chunk_text},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content
    tokens_used = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens,
    }

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response_text[start:end])
        else:
            data = {"entities": [], "relationships": []}

    return {
        "entities": data.get("entities", []),
        "relationships": data.get("relationships", []),
        "tokens": tokens_used,
    }
