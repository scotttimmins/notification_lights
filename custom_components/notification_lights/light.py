"""Colour light for each notification: pick its colour from the usual colour wheel."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NotificationEntity
from .printing import ring_url


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
    for item_id, runtime in hub.notifications.items():
        async_add_entities([ColourLight(runtime)], config_subentry_id=item_id)


class ColourLight(NotificationEntity, LightEntity):
    """The notification's colour, always shown, with the colour wheel to change it.

    A light only reports its colour while on, so this one is always on: it stands for the
    configured colour, not for whether the notification is showing (see the status
    attribute and the Active sensor). Choosing a colour saves it and previews it. Turning
    it on previews the notification; turning it off does nothing, use Dismiss.
    """

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, runtime) -> None:
        """Create the light."""
        super().__init__(runtime, "colour", "Colour")

    @property
    def is_on(self) -> bool:
        """Always on, so the colour is always visible."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add the plain-word status for the dashboard tile."""
        return {**super().extra_state_attributes, "status": self.runtime.status}

    @property
    def entity_picture(self) -> str:
        """A ring showing the notification's shape and position, in its colour."""
        return ring_url(self.runtime.footprint, self.runtime.rgb)

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
        """Do nothing: the colour does not switch off. Put the state back in the UI."""
        self.async_write_ha_state()
