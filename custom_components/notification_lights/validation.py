"""Pure validation for a Notification light (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .const import CONF_LIGHT, CONF_OFFSET, CONF_SEGMENTS


def validate_pick(light: str, other_lights: Iterable[str]) -> dict[str, str]:
    """Check the picked light is a ring and not already registered.

    Args:
        light: The picked light entity id.
        other_lights: Entity ids of the other registered lights.

    Returns:
        A map of field to error key; empty when valid.
    """
    if not light.endswith("_rgb"):
        return {CONF_LIGHT: "not_rgb"}
    if light in other_lights:
        return {CONF_LIGHT: "already_added"}
    return {}


def validate_priority(priority: int, other_priorities: Iterable[int]) -> dict[str, str]:
    """Check a priority is not used by another notification.

    Args:
        priority: The submitted priority.
        other_priorities: Priorities of the other notifications.

    Returns:
        A map of field to error key; empty when valid.
    """
    if priority in set(other_priorities):
        return {"priority": "priority_taken"}
    return {}


def validate_ring(user_input: dict[str, Any]) -> dict[str, str]:
    """Check the offset lies inside the ring.

    Args:
        user_input: The submitted form (segments and offset already ints).

    Returns:
        A map of field to error key; empty when valid.
    """
    if user_input[CONF_OFFSET] >= user_input[CONF_SEGMENTS]:
        return {CONF_OFFSET: "offset_too_large"}
    return {}
