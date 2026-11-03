"""Shared entity base for Notification Lights."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NOTIFICATIONS_PARENT
from .hub import NotificationRuntime


class NotificationEntity(Entity):
    """An entity belonging to one notification, refreshed when it changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: NotificationRuntime, key: str, name: str) -> None:
        """Create the entity.

        Args:
            runtime: The notification this entity belongs to.
            key: Suffix for the unique id.
            name: Entity name shown after the device name.
        """
        self.runtime = runtime
        self._attr_name = f"{runtime.name} {name}"
        self._attr_unique_id = f"{runtime.item_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{runtime.hub.entry.entry_id}_{NOTIFICATIONS_PARENT}")},
        )

    async def async_added_to_hass(self) -> None:
        """Follow the notification."""
        self.async_on_remove(self.runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        """Write the new state."""
        self.async_write_ha_state()
