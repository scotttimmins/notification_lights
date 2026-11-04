"""Shared entity base for Notification Lights."""

from __future__ import annotations

from typing import Any

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
        self._part = key
        self._attr_name = name
        self._attr_unique_id = f"{runtime.item_id}_{key}"
        # One device per notification, nested under Notifications: clicking it opens its entities.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.item_id)},
            name=runtime.name,
            manufacturer="Notification Lights",
            via_device=(DOMAIN, f"{runtime.hub.entry.entry_id}_{NOTIFICATIONS_PARENT}"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Tell the dashboard which notification and part this entity is."""
        return {"notification": self.runtime.name, "part": self._part}

    async def async_added_to_hass(self) -> None:
        """Follow the notification."""
        self.async_on_remove(self.runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        """Write the new state."""
        self.async_write_ha_state()
