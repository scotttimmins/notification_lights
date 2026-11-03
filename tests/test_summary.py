"""Why: the group screen is the only place all priorities and rooms are visible together."""

import _load  # noqa: F401

from notification_lights.summary import light_summary, notification_summary


def n(name, priority, scope="house", **extra):
    return {"name": name, "priority": priority, "footprint": "eighth_1", "scope": scope, **extra}


def test_notifications_listed_top_priority_first():
    # Lower numbers paint on top, so they must read first.
    text = notification_summary([n("Washing", 3), n("Fire", 1)])
    assert text.index("Fire") < text.index("Washing")


def test_scope_is_shown():
    text = notification_summary([n("Air", 8, "room", scope_area="dining_room")])
    assert "room dining room" in text


def test_empty_groups_say_so():
    assert "No notifications" in notification_summary([])
    assert "No notification lights" in light_summary([])


def test_light_without_rooms_is_house_only():
    assert "house only" in light_summary([{"light": "light.a_rgb", "areas": [], "floor": None}])
    text = light_summary([{"light": "light.d_rgb", "areas": ["dining_room", "kitchen"], "floor": "ground_floor"}])
    assert "dining room, kitchen, floor ground floor" in text


def test_light_listed_by_name_not_entity_id():
    # The name defaults to the entity's friendly name, so that is what people recognise.
    text = light_summary([{"light": "light.bed_rgb", "name": "Bedroom ring", "areas": ["bedroom"], "floor": None}])
    assert "Bedroom ring" in text and "light.bed_rgb" not in text
