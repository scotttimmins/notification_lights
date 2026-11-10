"""Notification Lights: show Aqara Light Notifications on T1M notification lights."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    GENERAL_DEVICE,
    KIND_LIGHT,
    KIND_NOTIFICATION,
    SERVICE_DISMISS_ALL,
    SERVICE_PRINT_SHEET,
)
from .hub import Hub
from . import ws
from .printing import GuideView, RingView, async_print_sheet

PLATFORMS = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.LIGHT]
STRATEGY_FILE = "notification-lights-strategy.js"

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

    async def _print_sheet(call: ServiceCall) -> ServiceResponse:
        return await async_print_sheet(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_PRINT_SHEET, _print_sheet, supports_response=SupportsResponse.ONLY
    )
    hass.http.register_view(GuideView())
    hass.http.register_view(RingView())
    ws.async_register(hass)
    await _register_dashboard_strategy(hass)
    return True


async def _register_dashboard_strategy(hass: HomeAssistant) -> None:
    """Serve the dashboard strategy and load it in the frontend.

    A dashboard then uses it with `strategy: {type: custom:notification-lights}`. The
    file's modified time is the cache-buster, so an update shows up without a hard refresh.

    Args:
        hass: Home Assistant instance.
    """
    path = Path(__file__).parent / "www" / STRATEGY_FILE
    url = f"/{DOMAIN}/{STRATEGY_FILE}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, str(path), cache_headers=False)]
    )
    version = await hass.async_add_executor_job(lambda: int(path.stat().st_mtime))
    add_extra_js_url(hass, f"{url}?v={version}")


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
    _create_general_device(hass, entry)
    hub = Hub(hass, entry)
    entry.runtime_data = hub
    await hub.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _prune_devices(hass, entry)
    # Adding, editing or removing a light or notification rebuilds everything.
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


def _create_general_device(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Create the entry-level device that holds Dismiss all and Print guide.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.
    """
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{GENERAL_DEVICE}")},
        name="Notification Lights",
        manufacturer="Notification Lights",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


def _prune_devices(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Remove the group devices of older layouts, after their entities have moved.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.
    """
    keep = {f"{entry.entry_id}_{GENERAL_DEVICE}", *entry.subentries}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        ours = {i for d, i in device.identifiers if d == DOMAIN}
        if ours and not ours & keep:
            registry.async_remove_device(device.id)


async def async_migrate_entry(
    hass: HomeAssistant, entry: NotificationLightsConfigEntry
) -> bool:
    """Move lights and notifications from the entry's options into subentries.

    Version 1 already had subentries. Version 2 kept the items in options; each becomes a
    subentry with the same id, so unique ids and entity ids survive and entities move onto
    the new per-item devices when the entry sets up.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.

    Returns:
        True when the entry is at the current version.
    """
    if entry.version < 3:
        for old_key, kind in (("lights", KIND_LIGHT), ("notifications", KIND_NOTIFICATION)):
            for item_id, data in entry.options.get(old_key, {}).items():
                hass.config_entries.async_add_subentry(
                    entry,
                    ConfigSubentry(
                        data=MappingProxyType(dict(data)),
                        subentry_type=kind,
                        title=data.get("name") or data["light"],
                        unique_id=None,
                        subentry_id=item_id,
                    ),
                )
        hass.config_entries.async_update_entry(entry, options={}, version=3)
    return True


async def _reload(hass: HomeAssistant, entry: NotificationLightsConfigEntry) -> None:
    """Reload after an option changed, unless the hub made the change itself (a colour)."""
    if entry.runtime_data.is_applied():
        return
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
