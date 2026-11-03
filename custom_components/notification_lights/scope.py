"""Does a notification reach a light (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable

from .const import SCOPE_FLOOR, SCOPE_HOUSE, SCOPE_ROOM


def applies(
    scope: str,
    scope_area: str | None,
    scope_floor: str | None,
    light_areas: Iterable[str],
    light_floor: str | None,
) -> bool:
    """Return whether a notification of this scope shows on a light.

    Args:
        scope: house, floor or room.
        scope_area: The notification's room (room scope).
        scope_floor: The notification's floor (floor scope).
        light_areas: The rooms the light belongs to.
        light_floor: The floor the light belongs to, if any.

    Returns:
        True when the light is in the notification's scope.
    """
    if scope == SCOPE_HOUSE:
        return True
    if scope == SCOPE_ROOM:
        return scope_area is not None and scope_area in set(light_areas)
    if scope == SCOPE_FLOOR:
        return scope_floor is not None and scope_floor == light_floor
    return False
