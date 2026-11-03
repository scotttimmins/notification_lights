"""Why: the same notification must look the same, in the same place, on every light."""

import _load  # noqa: F401

from notification_lights.footprint import FOOTPRINTS, segments_of, slots_of
from notification_lights.paint import build_pattern
from notification_lights.scope import applies
from notification_lights.validation import validate_priority

RED, BLUE, GREEN = [255, 0, 0], [0, 0, 255], [0, 255, 0]


def colours(pattern):
    return {p["segment"]: (p["color"]["r"], p["color"]["g"], p["color"]["b"]) for p in pattern}


def test_eighths_tile_a_26_led_ring_exactly():
    # No LED may be skipped or shared, or a footprint would bleed into its neighbour.
    covered = [i for n in range(1, 9) for i in segments_of(f"eighth_{n}", 26)]
    assert sorted(covered) == list(range(26))
    assert [len(segments_of(f"eighth_{n}", 26)) for n in range(1, 9)] == [3, 3, 3, 4, 3, 3, 3, 4]


def test_footprints_nest():
    # Every quarter is two eighths and every half is two quarters, so placement is stable.
    assert slots_of("quarter_2") == [2, 3]
    assert slots_of("half_1") == [0, 1, 2, 3]
    assert slots_of("half_2") == [2, 3, 4, 5]  # perpendicular orientation, quarter-aligned
    assert slots_of("half_4") == [6, 7, 0, 1]  # wraps round
    assert len(slots_of("whole")) == 8


def test_every_footprint_is_defined():
    for f in FOOTPRINTS:
        assert segments_of(f, 26)


def test_lower_priority_number_paints_on_top():
    # Fire (whole, priority 1) must cover a lower-priority eighth beneath it.
    p = colours(build_pattern(26, 0, [(5, "eighth_1", BLUE), (1, "whole", RED)]))
    assert set(p.values()) == {(255, 0, 0)}


def test_overlap_keeps_uncovered_part_of_lower_priority():
    p = colours(build_pattern(26, 0, [(1, "eighth_1", RED), (2, "half_1", GREEN)]))
    assert p[1] == (255, 0, 0) and p[4] == (0, 255, 0) and p[20] == (0, 0, 0)


def test_offset_rotates_the_picture():
    # Calibration: the same footprint must start offset LEDs further round on a rotated ring.
    p = colours(build_pattern(26, 2, [(1, "eighth_1", RED)]))
    assert {s for s, c in p.items() if c == (255, 0, 0)} == {3, 4, 5}
    p = colours(build_pattern(26, 25, [(1, "eighth_1", RED)]))
    assert {s for s, c in p.items() if c == (255, 0, 0)} == {26, 1, 2}


def test_nothing_to_show_gives_empty_pattern():
    assert build_pattern(26, 0, []) == []


def test_scope():
    # House reaches every light; room needs one of the light's rooms; floor needs its floor.
    assert applies("house", None, None, [], None)
    assert applies("room", "kitchen", None, ["dining_room", "kitchen"], None)
    assert not applies("room", "bedroom", None, ["dining_room", "kitchen"], None)
    assert applies("floor", None, "up", [], "up")
    assert not applies("floor", None, "up", [], None)


def test_priority_must_be_unique():
    # Ties would make paint order depend on creation order.
    assert validate_priority(3, [1, 2]) == {}
    assert validate_priority(2, [1, 2]) == {"priority": "priority_taken"}
