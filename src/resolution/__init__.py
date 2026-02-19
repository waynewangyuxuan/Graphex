"""Entity resolution module: embedding-based deduplication and parallel merge."""

from .entity_resolver import EntityResolver
from .parallel_merge import parallel_merge, merge_two_kgs

__all__ = ["EntityResolver", "parallel_merge", "merge_two_kgs"]
