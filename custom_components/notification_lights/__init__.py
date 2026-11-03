"""Notification Lights: show Aqara Light Notifications on T1M notification lights."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_DISMISS_ALL
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
    hub = Hub(hass, entry)
    entry.runtime_data = hub
    await hub.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Adding, editing or removing a light or notification rebuilds everything.
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


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
