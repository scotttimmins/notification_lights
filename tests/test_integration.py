"""Why: a notification must follow its source exactly and leave the room's main light alone."""

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.notification_lights.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations):
    yield


LIGHT = {
    "light": "light.bed_rgb",
    "areas": ["bedroom"],
    "floor": None,
    "segments": 26,
    "offset": 0,
    "brightness": 100,
    "quiet_hours": False,
    "idle_policy": "off",
}


def notification(name, priority, footprint, scope="house", **extra):
    return {
        "name": name,
        "colour": [255, 0, 0],
        "footprint": footprint,
        "priority": priority,
        "show_during_quiet_hours": False,
        "scope": scope,
        "delay": 0,
        "source_type": "entities",
        "source_entities": ["binary_sensor.door"],
        "source_state": "on",
        **extra,
    }


async def setup(hass, *notifications):
    hass.states.async_set("light.bed_rgb", "off")
    hass.states.async_set("binary_sensor.door", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        version=3,
        subentries_data=[
            ConfigSubentryData(
                subentry_type="light", title="Bed", unique_id=None, data=LIGHT, subentry_id="bed"
            ),
            *[
                ConfigSubentryData(
                    subentry_type="notification",
                    title=n["name"],
                    unique_id=None,
                    data=n,
                    subentry_id=f"n{i}",
                )
                for i, n in enumerate(notifications)
            ],
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_follows_source_and_clears(hass):
    paint = async_mock_service(hass, "aqara_advanced_lighting", "set_segment_pattern")
    off = async_mock_service(hass, "light", "turn_off")
    await setup(hass, notification("Door", 1, "eighth_1"))
    assert not paint

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert len(paint) == 1
    lit = {p["segment"] for p in paint[0].data["segment_colors"] if p["color"]["r"] == 255}
    assert lit == {1, 2, 3}

    hass.states.async_set("light.bed_rgb", "on")
    hass.states.async_set("binary_sensor.door", "off")
    await hass.async_block_till_done()
    assert len(off) == 1  # ring switched off once the notification ends


async def test_room_scope_skips_other_rooms(hass):
    paint = async_mock_service(hass, "aqara_advanced_lighting", "set_segment_pattern")
    async_mock_service(hass, "light", "turn_off")
    await setup(hass, notification("Kitchen", 1, "whole", "room", scope_area="kitchen"))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert not paint  # the ring is in the bedroom


async def test_dismiss_lasts_until_source_restarts(hass):
    paint = async_mock_service(hass, "aqara_advanced_lighting", "set_segment_pattern")
    async_mock_service(hass, "light", "turn_off")
    entry = await setup(hass, notification("Door", 1, "whole"))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert len(paint) == 1

    entry.runtime_data.dismiss_all()
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert len(paint) == 2  # shown again after the source restarted


async def test_migration_keeps_entity_ids_and_makes_subentries(hass):
    """Why: moving items into subentries must not delete entities users built automations on."""
    from homeassistant.helpers import entity_registry as er

    old = MockConfigEntry(
        domain=DOMAIN,
        data={},
        version=2,
        options={"notifications": {"door": notification("Door", 1, "whole")}},
    )
    old.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create("switch", DOMAIN, "door_enabled", config_entry=old)
    hass.states.async_set("binary_sensor.door", "off")
    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()
    assert old.version == 3 and not old.options
    assert old.subentries["door"].subentry_type == "notification"
    ent = registry.async_get_entity_id("switch", DOMAIN, "door_enabled")
    assert ent and registry.async_get(ent).config_subentry_id == "door"


async def test_each_notification_has_its_own_device_with_preview_and_dismiss(hass):
    """Why: the integration page shows one device per item; Preview and Dismiss live on it."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    entry = await setup(hass, notification("Door", 1, "whole"))
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "n0")})
    assert device and entry.entry_id in device.config_entries
    names = {e.original_name for e in er.async_entries_for_device(er.async_get(hass), device.id)}
    assert {"Preview", "Dismiss"} <= names


async def test_unknown_source_does_not_end_a_dismissal(hass):
    """Why: unknown is not inactive; a blip to unknown/unavailable must not bring it back."""
    paint = async_mock_service(hass, "aqara_advanced_lighting", "set_segment_pattern")
    async_mock_service(hass, "light", "turn_off")
    entry = await setup(hass, notification("Door", 1, "whole"))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    entry.runtime_data.dismiss_all()
    for blip in ("unavailable", "unknown", "on"):
        hass.states.async_set("binary_sensor.door", blip)
        await hass.async_block_till_done()
    assert entry.runtime_data.notifications["n0"].dismissed
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert not entry.runtime_data.notifications["n0"].dismissed


async def test_dismissal_survives_a_reload(hass):
    """Why: a restart while the source is still active must not light the ring again."""
    async_mock_service(hass, "aqara_advanced_lighting", "set_segment_pattern")
    async_mock_service(hass, "light", "turn_off")
    entry = await setup(hass, notification("Door", 1, "whole"))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    entry.runtime_data.dismiss_all()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.notifications["n0"].dismissed
