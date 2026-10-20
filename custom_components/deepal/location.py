"""Find a vehicle position in a condition payload.

The cloud does not document where (or whether) a position appears, so this
searches the payload for latitude/longitude keys pairs, case-insensitively and
at any depth. Experimental: the approach follows Sunek0/ha-deepal-alternative
(MIT), which itself ported it from dec_deepal; the code here is written for this
fork.
"""

from __future__ import annotations

from typing import Any

_LATITUDE_KEYS = frozenset({"lat", "latitude"})
_LONGITUDE_KEYS = frozenset({"lng", "lon", "longitude"})
_MAX_DEPTH = 6


def _coerce(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid(latitude: float, longitude: float) -> bool:
    """A usable position: in range and not the (0, 0) "no fix" value."""
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return False
    return not (latitude == 0.0 and longitude == 0.0)


def _pair(node: dict[str, Any]) -> tuple[float, float] | None:
    latitude = longitude = None
    for key, value in node.items():
        name = str(key).lower()
        if name in _LATITUDE_KEYS:
            latitude = _coerce(value)
        elif name in _LONGITUDE_KEYS:
            longitude = _coerce(value)
    if latitude is not None and longitude is not None and _valid(latitude, longitude):
        return latitude, longitude
    return None


def _walk(node: Any, path: str, depth: int):
    """Yield (path, (latitude, longitude)) for every valid pair, shallowest first."""
    if depth < 0:
        return
    if isinstance(node, dict):
        pair = _pair(node)
        if pair is not None:
            yield (path or "(top level)", pair)
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else str(key), depth - 1)
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            yield from _walk(item, f"{path}[{index}]", depth - 1)


def find_location(*sources: Any) -> tuple[float, float] | None:
    """Return the first valid (latitude, longitude) found in the sources."""
    for source in sources:
        for _path, pair in _walk(source, "", _MAX_DEPTH):
            return pair
    return None


def location_paths(*sources: Any) -> list[str]:
    """Return where positions were found (key names only, never the values)."""
    return [path for source in sources for path, _pair_value in _walk(source, "", _MAX_DEPTH)]
