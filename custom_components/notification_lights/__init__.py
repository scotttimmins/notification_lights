"""Notification Lights: show Aqara Light Notifications on T1M notification lights."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LIGHTS_PARENT, NOTIFICATIONS_PARENT, SERVICE_DISMISS_ALL
from .hub import Hub

PLATFORMS = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.BUTTON]

type NotificationLightsConfigEntry = ConfigEntry[Hub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the dismiss_all service.

    Args:
        hass: Home Assistant instance.
        config: Unused YAML config.

    Returns:
        True.
    """

    async def _dismiss_all(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            entry.runtime_data.dismiss_all()

    hass.services.async_register(DOMAIN, SERVICE_DISMISS_ALL, _dismiss_all)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NotificationLightsConfigEntry
) -> bool:
    """Start following sources and draw the lights.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.

    Returns:
        True when set up.
    """
    _create_parent_devices(hass, entry)
    hub = Hub(hass, entry)
    entry.runtime_data = hub
    await hub.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_old_device(hass, entry)
    # Adding, editing or removing a light or notification rebuilds everything.
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


def _create_parent_devices(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Create the two group devices every light and notification nests under.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.
    """
    registry = dr.async_get(hass)
    for key, name in ((LIGHTS_PARENT, "Notification lights"), (NOTIFICATIONS_PARENT, "Notifications")):
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{key}")},
            name=name,
            manufacturer="Notification Lights",
            entry_type=dr.DeviceEntryType.SERVICE,
        )


def _remove_old_device(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Drop the pre-grouping integration device once nothing is on it.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.
    """
    registry = dr.async_get(hass)
    old = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    if old and not er.async_entries_for_device(er.async_get(hass), old.id):
        registry.async_remove_device(old.id)


async def _reload(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Reload after a subentry or option changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: NotificationLightsConfigEntry
) -> bool:
    """Stop and put the lights back.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.

    Returns:
        True when unloaded.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
