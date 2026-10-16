"""Create sensors only once the vehicle actually reports them.

Cars differ in what they report (an S07 has no speed or gear, an S05 no outside
temperature, an E07 reports different signals again). Instead of creating every
sensor and leaving many "Unknown" forever, an entity is added once its data has
been seen, and added later if the data first appears later (for example when the
car wakes after an empty first report).

Entities that already exist in the entity registry for this config entry are
always kept, so upgrading never removes anything. A seen-set is stored so an
entity is not hidden again if its value is temporarily missing after a restart.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

Predicate = Callable[[dict[str, Any]], bool]
Candidate = tuple[Any, Predicate]


def partition(
    candidates: Iterable[Candidate],
    *,
    existing: set[str],
    seen: set[str],
    data: dict[str, Any],
) -> tuple[list[Any], list[Candidate]]:
    """Split candidates into (entities to add now, candidates still pending).

    An entity is added when it already exists in the registry, was seen before,
    or its predicate is true for the current data.
    """
    to_add: list[Any] = []
    pending: list[Candidate] = []
    for entity, supported in candidates:
        uid = entity.unique_id
        if uid in existing or uid in seen or supported(data):
            to_add.append(entity)
        else:
            pending.append((entity, supported))
    return to_add, pending


async def async_add_supported(
    hass: Any,
    entry: ConfigEntry,
    coordinator: Any,
    async_add_entities: AddEntitiesCallback,
    candidates: list[Candidate],
    platform: str,
) -> None:
    """Add the supported candidates now and the rest as soon as they are reported."""
    registry = er.async_get(hass)
    existing = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.domain == platform
    }
    store: Store[list[str]] = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_{platform}_seen")
    seen: set[str] = set((await store.async_load()) or [])

    to_add, pending = partition(candidates, existing=existing, seen=seen, data=coordinator.data or {})
    if to_add:
        async_add_entities(to_add)
        seen.update(entity.unique_id for entity in to_add)
        store.async_delay_save(lambda: sorted(seen), 5)

    if not pending:
        return

    @callback
    def _check() -> None:
        nonlocal pending
        newly, pending = partition(pending, existing=set(), seen=set(), data=coordinator.data or {})
        if not newly:
            return
        async_add_entities(newly)
        seen.update(entity.unique_id for entity in newly)
        store.async_delay_save(lambda: sorted(seen), 5)

    entry.async_on_unload(coordinator.async_add_listener(_check))
