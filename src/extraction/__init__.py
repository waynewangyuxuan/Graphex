"""Structured extraction module — single-call LLM entity + relationship extraction."""

from src.extraction.structured_extractor import extract_chunk
from src.extraction.merger import merge_chunk_results

__all__ = ["extract_chunk", "merge_chunk_results"]
