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


LIGHT = ConfigSubentryData(
    subentry_type="light",
    title="light.bed_rgb",
    unique_id="light.bed_rgb",
    data={
        "light": "light.bed_rgb",
        "areas": ["bedroom"],
        "floor": None,
        "segments": 26,
        "offset": 0,
        "brightness": 100,
        "quiet_hours": False,
        "idle_policy": "off",
    },
)


def notification(name, priority, footprint, scope="house", **extra):
    return ConfigSubentryData(
        subentry_type="notification",
        title=name,
        unique_id=None,
        data={
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
        },
    )


async def setup(hass, *notifications):
    hass.states.async_set("light.bed_rgb", "off")
    hass.states.async_set("binary_sensor.door", "off")
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, subentries_data=[LIGHT, *notifications]
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
