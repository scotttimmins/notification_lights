"""Plain-text summaries for the group screens (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .const import (
    CONF_AREAS,
    CONF_FLOOR,
    CONF_FOOTPRINT,
    CONF_LIGHT,
    CONF_NAME,
    CONF_PRIORITY,
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


def notification_label(data: Mapping[str, Any]) -> str:
    """Short label for a notification in a pick-list.

    Args:
        data: A notification's stored data.

    Returns:
        "<priority>. <name>".
    """
    return f"{data[CONF_PRIORITY]}. {data[CONF_NAME]}"


def notification_summary(items: Iterable[Mapping[str, Any]]) -> str:
    """List notifications by priority, highest (on top) first.

    Args:
        items: Stored data of every notification.

    Returns:
        One markdown bullet per notification, or a hint when there are none.
    """
    ordered = sorted(items, key=lambda d: int(d[CONF_PRIORITY]))
    if not ordered:
        return "No notifications yet."
    return "\n".join(
        f"- **{notification_label(d)}**: {_pretty(d[CONF_FOOTPRINT])}, {scope_text(d)}"
        for d in ordered
    )


def light_summary(items: Iterable[Mapping[str, Any]]) -> str:
    """List notification lights with the rooms and floor each belongs to.

    Args:
        items: Stored data of every notification light.

    Returns:
        One markdown bullet per light, or a hint when there are none.
    """
    ordered = sorted(items, key=lambda d: d.get(CONF_NAME) or d[CONF_LIGHT])
    if not ordered:
        return "No notification lights yet."
    lines = []
    for d in ordered:
        where = [_pretty(a) for a in d.get(CONF_AREAS) or []]
        if d.get(CONF_FLOOR):
            where.append(f"floor {_pretty(d[CONF_FLOOR])}")
        lines.append(
            f"- **{d.get(CONF_NAME) or d[CONF_LIGHT]}**: {', '.join(where) or 'house only'}"
        )
    return "\n".join(lines)
