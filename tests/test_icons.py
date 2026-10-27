"""icons.json must describe real entities and must not be shadowed by hard-coded icons."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "deepal"
ICONS = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))["entity"]
ENTITY_NAMES = json.loads((COMPONENT / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
ICON = re.compile(r"mdi:[a-z0-9-]+")


def _entries():
    for platform, keys in ICONS.items():
        for key, spec in keys.items():
            yield platform, key, spec


@pytest.mark.parametrize(("platform", "key", "spec"), list(_entries()))
def test_every_entry_is_a_real_entity_with_valid_icons(platform, key, spec):
    assert key in ENTITY_NAMES.get(platform, {}), "no entity with this translation key"
    assert ICON.fullmatch(spec["default"])
    for state_icon in spec.get("state", {}).values():
        assert ICON.fullmatch(state_icon)


def test_hard_coded_icons_would_override_icons_json():
    # An icon set in code wins over icons.json, so an entry here would never show.
    shadowed = []
    for path in COMPONENT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'Description\(\s*key="([a-z0-9_]+)"(.*?)\n    \),', text, re.S):
            key, body = match.groups()
            if 'icon="' in body and key in ICONS.get(path.stem, {}):
                shadowed.append((path.stem, key))
    assert not shadowed, shadowed
