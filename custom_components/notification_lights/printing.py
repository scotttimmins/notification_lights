"""Printable guide: the page, a signed link to it, and what the button and service do."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import web

from homeassistant.components import persistent_notification
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN
from .footprint import FOOTPRINTS, slots_of
from .guide import build_guide, ring_svg

GUIDE_PATH = f"/api/{DOMAIN}/guide"
RING_PATH = f"/api/{DOMAIN}/ring"
EVENT_PRINT_SHEET = f"{DOMAIN}_print_sheet"
LINK_LIFETIME = timedelta(minutes=10)


def render_guide(hass: HomeAssistant) -> str:
    """Build the guide from the running notifications and lights.

    Args:
        hass: Home Assistant instance.

    Returns:
        The HTML document (an empty guide when the integration is not loaded).
    """
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    hub = entries[0].runtime_data if entries else None
    notifications = [n.data for n in hub.notifications.values()] if hub else []
    lights = list(hub.lights.values()) if hub else []
    return build_guide(notifications, lights)


class GuideView(HomeAssistantView):
    """Serve the guide to a signed link (a browser tab cannot send a login header)."""

    url = GUIDE_PATH
    name = f"api:{DOMAIN}:guide"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Return the printable page."""
        return web.Response(text=render_guide(request.app[KEY_HASS]), content_type="text/html")


class RingView(HomeAssistantView):
    """Draw a footprint's ring as an icon, for the dashboard tile.

    Public on purpose: an image tag cannot send a login header, and the picture carries
    only a shape and a colour (no names), both given in the URL.
    """

    url = RING_PATH
    name = f"api:{DOMAIN}:ring"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the SVG for ?f=<footprint>&c=<rrggbb>."""
        footprint = request.query.get("f", "")
        colour = request.query.get("c", "")
        if footprint not in FOOTPRINTS or len(colour) != 6:
            return web.Response(status=400)
        try:
            rgb = [int(colour[i : i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            return web.Response(status=400)
        return web.Response(
            text=ring_svg(slots_of(footprint), rgb, icon=True), content_type="image/svg+xml"
        )


def ring_url(footprint: str, rgb: list[int]) -> str:
    """Return the icon URL for a footprint in a colour.

    Args:
        footprint: One of FOOTPRINTS.
        rgb: [r, g, b].

    Returns:
        A path under /api/notification_lights/ring.
    """
    return f"{RING_PATH}?f={footprint}&c={rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


async def async_print_sheet(hass: HomeAssistant, notify: bool = False) -> dict[str, Any]:
    """Make the guide available to print and announce it.

    A signed link (valid ten minutes) is created and fired as an event so an automation
    can hand it to a print integration. With notify, the link is also posted as a Home
    Assistant notification you can click.

    Args:
        hass: Home Assistant instance.
        notify: Also post a clickable notification (the button does; the service does not).

    Returns:
        The link and the document.
    """
    url = async_sign_path(hass, GUIDE_PATH, LINK_LIFETIME, use_content_user=True)
    try:
        full = f"{get_url(hass, prefer_external=False)}{url}"
    except NoURLAvailableError:
        full = url
    hass.bus.async_fire(EVENT_PRINT_SHEET, {"url": full})
    if notify:
        persistent_notification.async_create(
            hass,
            f"[Open the printable guide]({url})\n\nPrint it from your browser or save it as "
            "PDF. The link works for 10 minutes.",
            title="Notification lights guide",
            notification_id=f"{DOMAIN}_guide",
        )
    return {"url": full, "html": render_guide(hass)}
