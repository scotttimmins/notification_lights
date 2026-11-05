"""Plain-text helpers shared by the printable guide (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_SCOPE,
    CONF_SCOPE_AREA,
    CONF_SCOPE_FLOOR,
    SCOPE_FLOOR,
    SCOPE_ROOM,
)


def _pretty(value: str) -> str:
    """Make an id readable: dining_room becomes dining room."""
    return value.replace("_", " ")


def scope_text(data: Mapping[str, Any]) -> str:
    """Describe where a notification shows.

    Args:
        data: A notification's stored data.

    Returns:
        "house", "floor <name>" or "room <name>".
    """
    scope = data[CONF_SCOPE]
    if scope == SCOPE_ROOM:
        return f"room {_pretty(data.get(CONF_SCOPE_AREA) or '?')}"
    if scope == SCOPE_FLOOR:
        return f"floor {_pretty(data.get(CONF_SCOPE_FLOOR) or '?')}"
    return "house"
