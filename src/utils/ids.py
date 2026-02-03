"""
ID generation utilities.
"""

import uuid
from typing import Optional


def generate_id(prefix: Optional[str] = None) -> str:
    """
    Generate a unique ID.

    Args:
        prefix: Optional prefix for the ID

    Returns:
        Unique ID string
    """
    uid = uuid.uuid4().hex[:8]
    if prefix:
        return f"{prefix}_{uid}"
    return uid
