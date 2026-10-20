"""Device tracker for the vehicle position (experimental, opt-in).

Only created once the cloud actually returns a position, so it never appears on
cars or regions that do not report one.
"""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity
from .gating import async_add_supported


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    await async_add_supported(
        hass,
        entry,
        coordinator,
        async_add_entities,
        [(DeepalLocationTracker(coordinator), lambda data: bool(data.get("position")))],
        "device_tracker",
    )


class DeepalLocationTracker(DeepalEntity, TrackerEntity):
    """The vehicle's last known position."""

    _attr_translation_key = "location"
    _attr_name = "Location"
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "location")

    @property
    def _position(self) -> dict[str, float]:
        return (self.coordinator.data or {}).get("position") or {}

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._position.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self._position.get("longitude")
