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

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
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

# Bundled picture served when the API image is missing, slow or not an image, so
# the device page always has one (idea from Sunek0/ha-deepal-alternative, MIT).
GENERIC_ASSET = Path(__file__).parent / "assets" / "vehicle_generic.svg"
SVG_CONTENT_TYPE = "image/svg+xml"

# The API image is fetched in the background with a generous timeout, so a slow
# CDN does not matter; a request only waits a short time for it, well inside
# Home Assistant's 10 s image-proxy limit, then serves the fallback.
API_IMAGE_FETCH_TIMEOUT = 20
API_IMAGE_WAIT = 7
# After a failed fetch, serve the fallback without retrying for this long.
API_IMAGE_RETRY_AFTER = 60

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
        self._fallback_bytes: bytes | None = None
        self._failed_at: float | None = None
        self._fetch_task: asyncio.Task[bytes | None] | None = None
        self._warned = False
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
        if self._last_url:
            self._async_start_fetch()

    async def async_will_remove_from_hass(self) -> None:
        if self._fetch_task is not None and not self._fetch_task.done():
            self._fetch_task.cancel()
        await super().async_will_remove_from_hass()

    def _handle_coordinator_update(self) -> None:
        current_url = self._source_url
        if current_url and current_url != self._last_url:
            self._last_url = current_url
            self._image_bytes = None  # force a re-fetch on next async_image()
            self._failed_at = None
            self._attr_image_last_updated = datetime.now(timezone.utc)
            self._async_start_fetch()
        super()._handle_coordinator_update()

    async def _async_fallback(self) -> bytes | None:
        """Return the bundled fallback picture, reading it once."""
        if self._fallback_bytes is None:
            try:
                self._fallback_bytes = await self.hass.async_add_executor_job(GENERIC_ASSET.read_bytes)
            except OSError as err:
                _LOGGER.error("Deepal: bundled vehicle image %s is missing: %s", GENERIC_ASSET, err)
                return None
        if self._attr_content_type != SVG_CONTENT_TYPE:
            self._attr_content_type = SVG_CONTENT_TYPE
            self._attr_image_last_updated = datetime.now(timezone.utc)
        return self._fallback_bytes

    def _async_start_fetch(self) -> None:
        """Start the background API image fetch unless one is already running."""
        if self._fetch_task is not None and not self._fetch_task.done():
            return
        self._fetch_task = self.hass.async_create_background_task(
            self._async_fetch_api_image(), name="deepal_vehicle_image"
        )

    async def _async_fetch_api_image(self) -> bytes | None:
        """Download and validate the API image; any failure leaves the fallback."""
        url = self._source_url
        if not url:
            return None
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=API_IMAGE_FETCH_TIMEOUT)
            ) as response:
                response.raise_for_status()
                data = await response.read()
            content_type = _sniff_content_type(data)
            if content_type is None:
                raise ValueError(f"not a recognised image ({len(data)} bytes)")
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - any failure falls back to the bundled picture
            self._failed_at = time.monotonic()
            # Warn once so a persistent problem is visible; later retries are quiet.
            log = _LOGGER.debug if self._warned else _LOGGER.warning
            self._warned = True
            log("Deepal: vehicle image fetch failed (%s: %s); using the bundled picture", type(err).__name__, err)
            return None
        self._image_bytes = data
        self._failed_at = None
        self._warned = False
        self._attr_content_type = content_type
        self._attr_image_last_updated = datetime.now(timezone.utc)
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()
        return data

    async def async_image(self) -> bytes | None:
        """Return the API image, or the bundled fallback if it is unavailable."""
        if self._image_bytes is not None:
            return self._image_bytes
        if not self._source_url:
            return await self._async_fallback()
        if self._failed_at is not None and time.monotonic() - self._failed_at < API_IMAGE_RETRY_AFTER:
            return await self._async_fallback()
        self._async_start_fetch()
        try:
            data = await asyncio.wait_for(asyncio.shield(self._fetch_task), timeout=API_IMAGE_WAIT)
        except TimeoutError:
            data = None
        return data if data is not None else await self._async_fallback()
