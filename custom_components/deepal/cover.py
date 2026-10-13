"""Cover platform: removes the retired window and boot covers.

Windows and boot are now explicit buttons (see button.py): a cover's up arrow
means "open", which for windows means lowering them, and a stray tap on a cover
is easy to make. This platform creates no entities; it only removes the old
cover entries from the entity registry so they do not linger as unavailable.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DeepalDataUpdateCoordinator

RETIRED_COVER_KEYS = ("windows_cover", "boot_cover")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    registry = er.async_get(hass)
    for key in RETIRED_COVER_KEYS:
        entity_id = registry.async_get_entity_id("cover", DOMAIN, f"{coordinator.vehicle_id}_{key}")
        if entity_id:
            registry.async_remove(entity_id)
