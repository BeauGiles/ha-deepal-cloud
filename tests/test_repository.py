"""Guards for repository metadata mistakes that already happened once."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "deepal"


def load(relative):
    return json.loads((COMPONENT / relative).read_text())


def test_manifest_has_no_unused_bluetooth_entries():
    # A bluetooth matcher needs a config-flow bluetooth step; this integration has none.
    manifest = load("manifest.json")
    assert "bluetooth" not in manifest
    assert "dependencies" not in manifest


def test_manifest_basics():
    manifest = load("manifest.json")
    assert manifest["domain"] == "deepal"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "device"
    assert manifest["version"]


@pytest.mark.parametrize("name", ["strings.json", "translations/en.json"])
def test_json_files_parse(name):
    load(name)


def test_english_translation_matches_strings():
    # Hassfest/HA read translations/en.json; strings.json is the source of truth.
    assert load("strings.json")["entity"] == load("translations/en.json")["entity"]


def test_every_platform_module_exists():
    # A declared platform without a module hard-fails the whole entry (this broke 0.3.5).
    source = (COMPONENT / "const.py").read_text()
    platforms = [
        line.split("Platform.")[1].rstrip(",").lower()
        for line in source.splitlines()
        if line.strip().startswith("Platform.")
    ]
    assert platforms
    for platform in platforms:
        assert (COMPONENT / f"{platform}.py").exists(), platform


def test_fallback_image_is_bundled():
    assert (COMPONENT / "assets" / "vehicle_generic.png").exists()
