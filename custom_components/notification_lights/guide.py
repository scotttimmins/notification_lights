"""The printable guide: what each notification looks like and where (no Home Assistant imports)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from html import escape
from typing import Any

from .const import (
    CONF_AREAS,
    CONF_COLOUR,
    CONF_DELAY,
    CONF_FLOOR,
    CONF_FOOTPRINT,
    CONF_LIGHT,
    CONF_NAME,
    CONF_PRIORITY,
    CONF_SOURCE_ENTITIES,
    CONF_SOURCE_STATE,
    CONF_SOURCE_TYPE,
    SOURCE_TEMPLATE,
)
from .footprint import SLOTS, slots_of
from .summary import _pretty, scope_text

_STYLE = """
body{font-family:system-ui,Arial,sans-serif;margin:24px;color:#111}
h1{margin:0 0 4px}
.hint{color:#555;margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{border:1px solid #bbb;border-radius:8px;padding:12px;break-inside:avoid;display:flex;gap:12px}
.card svg{width:110px;height:110px;flex:none}
.card h3{margin:0 0 6px;font-size:16px}
.card p{margin:3px 0;font-size:13px}
.swatch{display:inline-block;width:14px;height:14px;border:1px solid #333;vertical-align:-2px;margin-right:5px}
h2{margin:26px 0 8px;break-after:avoid}
li{margin:3px 0}
.foot{color:#555;font-size:12px;margin-top:18px}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
@media print{.hint{display:none}body{margin:10mm}}
"""


def _hex(rgb: Iterable[int]) -> str:
    """Format [r, g, b] as #rrggbb."""
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _polar(radius: float, angle: float) -> tuple[float, float]:
    """Point on the ring (centre 60,60) at an angle in radians."""
    return 60 + radius * math.cos(angle), 60 + radius * math.sin(angle)


def ring_svg(slots: Iterable[int], rgb: Iterable[int]) -> str:
    """Draw the ring seen from below, with the lit slots in the notification's colour.

    Slot 1 is at the top and slots run clockwise, numbered as on the light.

    Args:
        slots: Slot numbers (0-7) that are lit.
        rgb: The notification's colour.

    Returns:
        An inline SVG string.
    """
    lit = set(slots)
    fill_on = _hex(rgb)
    gap = 0.035
    parts = []
    for s in range(SLOTS):
        a0 = -math.pi / 2 + s * 2 * math.pi / SLOTS + gap
        a1 = -math.pi / 2 + (s + 1) * 2 * math.pi / SLOTS - gap
        ox0, oy0 = _polar(54, a0)
        ox1, oy1 = _polar(54, a1)
        ix1, iy1 = _polar(30, a1)
        ix0, iy0 = _polar(30, a0)
        d = (
            f"M{ox0:.2f},{oy0:.2f} A54,54 0 0 1 {ox1:.2f},{oy1:.2f} "
            f"L{ix1:.2f},{iy1:.2f} A30,30 0 0 0 {ix0:.2f},{iy0:.2f} Z"
        )
        parts.append(
            f'<path d="{d}" fill="{fill_on if s in lit else "#ececec"}" '
            f'stroke="#555" stroke-width="0.8"/>'
        )
        lx, ly = _polar(42, (a0 + a1) / 2)
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="8" text-anchor="middle" '
            f'dominant-baseline="central" fill="#000" stroke="#fff" stroke-width="2" '
            f'paint-order="stroke">{s + 1}</text>'
        )
    return f'<svg viewBox="0 0 120 120" role="img">{"".join(parts)}</svg>'


def _raised_when(data: Mapping[str, Any]) -> str:
    """Describe the source in words."""
    if data.get(CONF_SOURCE_TYPE) == SOURCE_TEMPLATE:
        text = "a custom template is true"
    else:
        entities = ", ".join(data.get(CONF_SOURCE_ENTITIES) or [])
        text = f"any of {entities} is “{data.get(CONF_SOURCE_STATE, 'on')}”"
    delay = int(data.get(CONF_DELAY) or 0)
    return f"{text}, for {delay} s" if delay else text


def _card(data: Mapping[str, Any]) -> str:
    """One notification card."""
    footprint = data[CONF_FOOTPRINT]
    numbers = ", ".join(str(s + 1) for s in sorted(slots_of(footprint)))
    colour = _hex(data[CONF_COLOUR])
    return (
        '<div class="card">'
        f"{ring_svg(slots_of(footprint), data[CONF_COLOUR])}"
        "<div>"
        f'<h3>{escape(str(data[CONF_PRIORITY]))}. {escape(data[CONF_NAME])}</h3>'
        f'<p><span class="swatch" style="background:{colour}"></span>{colour}</p>'
        f"<p><b>Section:</b> {escape(_pretty(footprint))} (slots {numbers})</p>"
        f"<p><b>Shows:</b> {escape(scope_text(data))}</p>"
        f"<p><b>When:</b> {escape(_raised_when(data))}</p>"
        "</div></div>"
    )


def build_guide(
    notifications: Iterable[Mapping[str, Any]],
    lights: Iterable[Mapping[str, Any]],
    title: str = "Notification lights guide",
) -> str:
    """Build the printable guide as one self-contained HTML document.

    Args:
        notifications: Stored data of every notification.
        lights: Stored data of every notification light.
        title: Page title.

    Returns:
        An HTML document; notifications are listed highest priority first.
    """
    ordered = sorted(notifications, key=lambda d: int(d[CONF_PRIORITY]))
    cards = "".join(_card(d) for d in ordered) or "<p>No notifications yet.</p>"
    items = []
    for d in sorted(lights, key=lambda d: d.get(CONF_NAME) or d[CONF_LIGHT]):
        where = [_pretty(a) for a in d.get(CONF_AREAS) or []]
        if d.get(CONF_FLOOR):
            where.append(f"floor {_pretty(d[CONF_FLOOR])}")
        items.append(
            f"<li><b>{escape(d.get(CONF_NAME) or d[CONF_LIGHT])}</b>: "
            f"{escape(', '.join(where) or 'house only')}</li>"
        )
    lights_html = f"<h2>Notification lights</h2><ul>{''.join(items)}</ul>" if items else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        '<p class="hint">Print this page from your browser (Ctrl+P or Cmd+P) or save it as PDF. '
        "If the colours are missing, turn on background graphics in the print dialog.</p>"
        f'<div class="grid">{cards}</div>{lights_html}'
        '<p class="foot">Each ring is seen from below. Slot 1 is at the top and slots run clockwise; '
        "the coloured slots are where the notification shows on the light. "
        "A notification with a lower number shows on top of one with a higher number.</p>"
        "</body></html>"
    )
