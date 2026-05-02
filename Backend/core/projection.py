"""Snake_case → camelCase wire-format helpers for Postgres routers.

The DB returns RealDictCursor rows with snake_case keys (matching schema.sql).
The frontend wire format is camelCase (CONSTITUTION §4 — "camelCase wire format
preserved across the migration"). `to_camel()` is the bridge.

This module is intentionally side-effect free at import.
"""

from typing import Optional


def _camelize(snake: str) -> str:
    """Convert one snake_case identifier to camelCase.

    Edge cases:
      - no underscore: returned unchanged ("name" → "name")
      - leading underscore: empty head + remaining parts ("_id" → "Id")
      - trailing underscore: head + empty tail ("end_" → "end")
      - consecutive underscores: empty parts collapse ("a__b" → "aB")
    """
    if "_" not in snake:
        return snake
    head, *tail = snake.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in tail)


def to_camel(row: Optional[dict]) -> Optional[dict]:
    """Convert top-level snake_case keys of a dict to camelCase.

    Returns None if input is None (RealDictCursor.fetchone() returns None for
    no-match queries — a router can pass that result straight through).

    Does NOT recurse into nested dicts/lists. JSONB columns already store
    application-controlled JSON; their contents pass through unchanged.
    """
    if row is None:
        return None
    return {_camelize(k): v for k, v in row.items()}
