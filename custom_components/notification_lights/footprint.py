"""Footprints on the 8-slot grid (no Home Assistant imports).

A footprint is the part of a Notification light a notification paints: the whole
light, a half, a quarter or an eighth. Halves start on a quarter boundary, so there
are four of them (two perpendicular orientations) and they overlap.
"""

from __future__ import annotations

SLOTS = 8

FOOTPRINTS = (
    ["whole"]
    + [f"half_{i}" for i in range(1, 5)]
    + [f"quarter_{i}" for i in range(1, 5)]
    + [f"eighth_{i}" for i in range(1, 9)]
)


def slots_of(footprint: str) -> list[int]:
    """Return the grid slots (0-7) a footprint covers.

    Args:
        footprint: One of FOOTPRINTS.

    Returns:
        Slot numbers, wrapping past slot 7 back to 0.
    """
    if footprint == "whole":
        return list(range(SLOTS))
    kind, _, number = footprint.partition("_")
    index = int(number) - 1
    length = {"half": 4, "quarter": 2, "eighth": 1}[kind]
    step = {"half": 2, "quarter": 2, "eighth": 1}[kind]
    start = index * step
    return [(start + i) % SLOTS for i in range(length)]


def segments_of(footprint: str, segments: int) -> list[int]:
    """Return the ring positions (0-based, before any offset) a footprint covers.

    A slot covers positions segments*slot//8 up to segments*(slot+1)//8, so a
    26-LED ring gives slots of 3 or 4 LEDs.

    Args:
        footprint: One of FOOTPRINTS.
        segments: LEDs on the ring.

    Returns:
        Ring positions in ascending order of slot.
    """
    out: list[int] = []
    for slot in slots_of(footprint):
        out.extend(range(segments * slot // SLOTS, segments * (slot + 1) // SLOTS))
    return out
