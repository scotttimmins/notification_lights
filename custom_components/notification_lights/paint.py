"""Compose what a Notification light shows (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .footprint import segments_of


def build_pattern(
    segments: int,
    offset: int,
    layers: Iterable[tuple[int, str, list[int]]],
) -> list[dict[str, Any]]:
    """Paint layers onto a ring and return the segment colours to send.

    Lower priority numbers paint on top. Unpainted segments are black. The offset
    rotates the picture so a footprint starts at segment offset + 1.

    Args:
        segments: LEDs on the ring.
        offset: LEDs to rotate the picture by.
        layers: (priority, footprint, [r, g, b]) for everything to show.

    Returns:
        One {segment, color} per LED, or an empty list when there are no layers.
    """
    ordered = sorted(layers, key=lambda layer: layer[0], reverse=True)
    if not ordered:
        return []
    colours: list[list[int]] = [[0, 0, 0] for _ in range(segments)]
    for _priority, footprint, rgb in ordered:
        for position in segments_of(footprint, segments):
            colours[position] = rgb
    return [
        {
            "segment": (position + offset) % segments + 1,
            "color": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
        }
        for position, rgb in enumerate(colours)
    ]
