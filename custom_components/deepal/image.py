"""Vehicle image entity for Deepal vehicles.

Ported from the original BeauGiles/ha-deepal repo (new fork only exposed the
image URL as a diagnostic sensor string, with no rendered picture entity).

Home Assistant's built-in ImageEntity.image_url path fetches via httpx and then
requires the response's Content-Type header to start with "image/" (see
homeassistant.components.image._async_load_image_from_url / valid_image_content_type).
The Deepal CDN serves vehicle photos from a hash-obfuscated path
(.../cdnshamdown/...) that doesn't reliably return that header, even though the
bytes are a perfectly valid image - a browser renders it fine because browsers
sniff the file's magic bytes instead of trusting the header. So instead of using
image_url, this entity fetches the bytes itself and sniffs the format directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity

_LOGGER = logging.getLogger(__name__)

# Magic-byte signatures for the image formats Deepal is known to serve.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # WEBP: RIFF....WEBP - good enough as a prefix check
)


def _sniff_content_type(data: bytes) -> str | None:
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    async_add_entities([DeepalVehicleImage(hass, coordinator)])


class DeepalVehicleImage(DeepalEntity, ImageEntity):
    """Renders the vehicle photo supplied by the Deepal API."""

    _attr_translation_key = "vehicle_image"
    _attr_name = "Vehicle Image"

    def __init__(self, hass: HomeAssistant, coordinator: DeepalDataUpdateCoordinator) -> None:
        DeepalEntity.__init__(self, coordinator, "vehicle_image")
        ImageEntity.__init__(self, hass)
        self._session = async_get_clientsession(hass)
        self._last_url: str | None = None
        self._image_bytes: bytes | None = None
        self._attr_image_last_updated = datetime.now(timezone.utc)
        # Deliberately NOT setting image_url: HA's own fetch path enforces a strict
        # image/* Content-Type header that this CDN doesn't reliably send. We fetch
        # and sniff bytes ourselves in async_image() instead.

    @property
    def _vehicle(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("vehicle") or {}

    @property
    def _source_url(self) -> str | None:
        return self._vehicle.get("imgUrl")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._last_url = self._source_url

    def _handle_coordinator_update(self) -> None:
        current_url = self._source_url
        if current_url and current_url != self._last_url:
            self._last_url = current_url
            self._image_bytes = None  # force a re-fetch on next async_image()
            self._attr_image_last_updated = datetime.now(timezone.utc)
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if self._image_bytes is not None:
            return self._image_bytes
        url = self._source_url
        if not url:
            return None
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                data = await response.read()
        except Exception as err:  # noqa: BLE001 - log and surface as "no image" rather than crash
            _LOGGER.warning("Deepal: failed to fetch vehicle image from %s: %s", url, err)
            return None
        content_type = _sniff_content_type(data)
        if content_type is None:
            _LOGGER.warning(
                "Deepal: vehicle image from %s did not match a known image format (got %d bytes)",
                url,
                len(data),
            )
            return None
        self._attr_content_type = content_type
        self._image_bytes = data
        return data
