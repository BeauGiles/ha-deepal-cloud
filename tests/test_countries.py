"""The country table is the single source: hacs.json and the README must agree with it."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from custom_components.deepal.const import BASE_URL, DEFAULT_COUNTRY, REGIONS, region_for_country
from custom_components.deepal.countries import COUNTRIES, REGION_APAC, REGION_EUROPE

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_table_is_well_formed():
    assert DEFAULT_COUNTRY in COUNTRIES
    for code, country in COUNTRIES.items():
        assert code == country.code and re.fullmatch(r"[A-Z]{2}", code)
        assert country.dial_code.isdigit()
        assert country.region in {REGION_EUROPE, REGION_APAC}
        assert country.label == f"{country.name} (+{country.dial_code})"


def test_every_region_used_has_hosts():
    assert {c.region for c in COUNTRIES.values()} <= set(REGIONS)
    for region in REGIONS.values():
        assert set(region) == {"base_url", "sda_base_url", "gateway"}


def test_routing_follows_the_table():
    assert region_for_country("GB")["base_url"] == BASE_URL
    assert region_for_country("au") == REGIONS[REGION_APAC]  # case-insensitive
    assert region_for_country("AU")["gateway"] == "/appgw"
    for code, country in COUNTRIES.items():
        assert region_for_country(code) == REGIONS[country.region]


def test_unknown_or_missing_country_uses_the_default_cluster():
    assert region_for_country(None) == region_for_country("") == region_for_country("ZZ")
    assert region_for_country("ZZ")["base_url"] == BASE_URL


def test_hacs_json_lists_exactly_these_countries():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert set(hacs["country"]) == set(COUNTRIES)


@pytest.mark.parametrize("country", list(COUNTRIES.values()), ids=list(COUNTRIES))
def test_readme_mentions_every_country(country):
    assert country.name in README


def test_readme_confirmed_list_matches_the_verified_flags():
    line = next(text for text in README.splitlines() if text.startswith("* **Confirmed working:**"))
    for country in COUNTRIES.values():
        assert (country.name in line) == country.verified, country.name
