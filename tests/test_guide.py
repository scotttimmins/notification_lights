"""Why: the sheet is how someone learns what a colour on the ceiling means, so it must be right."""

import _load  # noqa: F401

from notification_lights.guide import build_guide, ring_svg


def n(name, priority, footprint, colour=(255, 0, 0), **extra):
    return {
        "name": name, "priority": priority, "footprint": footprint, "colour": list(colour),
        "scope": "house", "source_type": "entities", "source_entities": ["binary_sensor.door"],
        "source_state": "on", "delay": 0, **extra,
    }


def test_lists_highest_priority_first_with_colour_and_section():
    html = build_guide([n("Washing", 3, "eighth_1", (0, 255, 255)), n("Fire", 1, "whole")], [])
    assert html.index("Fire") < html.index("Washing")
    assert "#00ffff" in html and "eighth 1 (slots 1)" in html


def test_only_the_notifications_slots_are_coloured():
    # Eighth 3 is slot 3 only: exactly one of the eight wedges takes the colour.
    svg = ring_svg([2], [10, 20, 30])
    assert svg.count('fill="#0a141e"') == 1 and svg.count('fill="#ececec"') == 7


def test_names_are_escaped():
    # A name is user text going into a page opened in the browser.
    html = build_guide([n("<script>alert(1)</script>", 1, "whole")], [])
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_source_and_delay_are_described():
    html = build_guide([n("Fridge", 5, "eighth_3", delay=300, source_entities=["binary_sensor.fridge"])], [])
    assert "binary_sensor.fridge" in html and "for 300 s" in html


def test_lights_listed_and_empty_message():
    html = build_guide([], [{"light": "light.d_rgb", "name": "Dining", "areas": ["dining_room", "kitchen"], "floor": None}])
    assert "No notifications yet" in html and "dining room, kitchen" in html
