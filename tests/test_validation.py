"""Why: a wrongly picked light (main light, duplicate) or a bad offset breaks placement."""


import _load  # noqa: F401

from notification_lights.validation import validate_pick, validate_ring


def test_ring_light_accepted():
    assert validate_pick("light.bed_rgb", []) == {}


def test_main_light_rejected():
    # The central room light must never be taken over (CONTEXT: Notification light).
    assert validate_pick("light.bed", []) == {"light": "not_rgb"}


def test_duplicate_rejected():
    assert validate_pick("light.bed_rgb", ["light.bed_rgb"]) == {"light": "already_added"}


def test_offset_must_be_inside_ring():
    assert validate_ring({"segments": 26, "offset": 26}) == {"offset": "offset_too_large"}
    assert validate_ring({"segments": 26, "offset": 25}) == {}
