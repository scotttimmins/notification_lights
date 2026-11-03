"""Active sensor for each notification."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NotificationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an Active sensor per notification.

    Args:
        hass: Home Assistant instance.
        entry: The integration's config entry.
        async_add_entities: Callback to add entities.
    """
    hub = entry.runtime_data
    for item_id, runtime in hub.notifications.items():
        async_add_entities([ActiveSensor(runtime)])


class ActiveSensor(NotificationEntity, BinarySensorEntity):
    """On while the notification is showing on its lights."""

    def __init__(self, runtime) -> None:
        """Create the sensor."""
        super().__init__(runtime, "active", "Active")

    @property
    def is_on(self) -> bool:
        """Whether the notification is showing."""
        return self.runtime.showing

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Why it is or is not showing."""
        r = self.runtime
        return {
            "enabled": r.enabled,
            "source_active": r.source_active,
            "dismissed": r.dismissed,
            "previewing": r.previewing,
            "priority": r.priority,
            "footprint": r.footprint,
        }
