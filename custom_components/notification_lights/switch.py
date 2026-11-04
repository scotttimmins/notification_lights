"""Enabled switch for each notification."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import NotificationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an Enabled switch per notification.

    Args:
        hass: Home Assistant instance.
        entry: The integration's config entry.
        async_add_entities: Callback to add entities.
    """
    hub = entry.runtime_data
    for item_id, runtime in hub.notifications.items():
        async_add_entities([EnabledSwitch(runtime)], config_subentry_id=item_id)


class EnabledSwitch(NotificationEntity, SwitchEntity, RestoreEntity):
    """Persistent on/off for a notification. Off hides it until turned back on."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime) -> None:
        """Create the switch."""
        super().__init__(runtime, "enabled", "Enabled")

    async def async_added_to_hass(self) -> None:
        """Restore the last enabled state."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.runtime.set_enabled(last.state != STATE_OFF)

    @property
    def is_on(self) -> bool:
        """Whether the notification is enabled."""
        return self.runtime.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the notification."""
        self.runtime.set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the notification."""
        self.runtime.set_enabled(False)
