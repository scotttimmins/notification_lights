"""Preview and Dismiss buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_NAME, DOMAIN, LIGHTS_PARENT, NOTIFICATIONS_PARENT
from .entity import NotificationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Preview and Dismiss per notification, Preview per light, and Dismiss all.

    Args:
        hass: Home Assistant instance.
        entry: The integration's config entry.
        async_add_entities: Callback to add entities.
    """
    hub = entry.runtime_data
    for item_id, runtime in hub.notifications.items():
        async_add_entities([PreviewButton(runtime), DismissButton(runtime)])
    for item_id, light in hub.lights.items():
        async_add_entities(
            [LightPreviewButton(hub, entry, item_id, light.get(CONF_NAME) or light["light"])]
        )
    async_add_entities([DismissAllButton(hub, entry)])


class PreviewButton(NotificationEntity, ButtonEntity):
    """Show the notification on its lights for 30 seconds."""

    def __init__(self, runtime) -> None:
        """Create the button."""
        super().__init__(runtime, "preview", "Preview")

    async def async_press(self) -> None:
        """Preview the notification."""
        self.runtime.preview()


class DismissButton(NotificationEntity, ButtonEntity):
    """Hide the notification until its source next starts."""

    def __init__(self, runtime) -> None:
        """Create the button."""
        super().__init__(runtime, "dismiss", "Dismiss")

    async def async_press(self) -> None:
        """Dismiss the notification."""
        self.runtime.dismiss()


class LightPreviewButton(ButtonEntity):
    """Show eighth 1 on a light for 30 seconds, to calibrate its offset."""

    _attr_has_entity_name = True

    def __init__(self, hub, entry: ConfigEntry, item_id: str, light: str) -> None:
        """Create the button.

        Args:
            hub: The hub.
            entry: The integration config entry.
            item_id: The light's id.
            light: The light's display name.
        """
        self._hub = hub
        self._item_id = item_id
        self._attr_unique_id = f"{item_id}_preview"
        self._attr_name = f"{light} calibration preview"
        self._attr_extra_state_attributes = {"part": "calibration", "light": light}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{LIGHTS_PARENT}")}
        )

    async def async_press(self) -> None:
        """Preview eighth 1."""
        self._hub.preview_light(self._item_id)


class DismissAllButton(ButtonEntity):
    """Dismiss every active notification."""

    _attr_has_entity_name = True
    _attr_name = "Dismiss all"
    _attr_extra_state_attributes = {"part": "dismiss_all"}

    def __init__(self, hub, entry: ConfigEntry) -> None:
        """Create the button.

        Args:
            hub: The hub.
            entry: The integration's config entry.
        """
        self._hub = hub
        self._attr_unique_id = f"{entry.entry_id}_dismiss_all"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{NOTIFICATIONS_PARENT}")}
        )

    async def async_press(self) -> None:
        """Dismiss all."""
        self._hub.dismiss_all()
