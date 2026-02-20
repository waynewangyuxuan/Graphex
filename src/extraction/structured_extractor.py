"""Single-call structured extraction: one LLM call → entities + relationships.

Pattern: CocoIndex-style ExtractByLlm (ADR-0003).
"""

import json
from typing import Optional

import litellm

from src.extraction.prompts import PROMPTS, CHUNK_PROMPT


def extract_chunk(
    chunk_text: str,
    model: str = "gemini/gemini-2.5-flash-lite-preview-09-2025",
    prompt: Optional[str] = None,
) -> dict:
    """
    Extract entities and relationships from text.

    Args:
        chunk_text: The text to extract from (chunk or whole document).
        model: LiteLLM model identifier.
        prompt: Prompt name from PROMPTS registry, or raw prompt string.
                Defaults to "chunk".

    Returns dict with keys: entities, relationships, tokens.
    """
    if prompt is None:
        system_prompt = CHUNK_PROMPT
    elif prompt in PROMPTS:
        system_prompt = PROMPTS[prompt]
    else:
        system_prompt = prompt  # allow raw prompt string

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
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
