"""Colour light for each notification: pick its colour from the usual colour wheel."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NotificationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a Colour light per notification.

    Args:
        hass: Home Assistant instance.
        entry: The integration's config entry.
        async_add_entities: Callback to add entities.
    """
    hub = entry.runtime_data
    async_add_entities([ColourLight(runtime) for runtime in hub.notifications.values()])


class ColourLight(NotificationEntity, LightEntity):
    """A notification seen as a light: on while showing, in the notification's colour.

    Choosing a colour saves it and previews it on the lights. Turning it on previews the
    notification, and turning it off dismisses it.
    """

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, runtime) -> None:
        """Create the light."""
        super().__init__(runtime, "colour", "Colour")

    @property
    def is_on(self) -> bool:
        """Whether the notification is showing."""
        return self.runtime.showing

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """The notification's colour."""
        r, g, b = self.runtime.rgb
        return (r, g, b)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Save a chosen colour, or preview the notification.

        Args:
            **kwargs: Light service data; only rgb_color is used.
        """
        if ATTR_RGB_COLOR in kwargs:
            self.runtime.hub.set_colour(
                self.runtime.item_id, [int(c) for c in kwargs[ATTR_RGB_COLOR]]
            )
        else:
            self.runtime.preview()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Dismiss the notification."""
        self.runtime.dismiss()
